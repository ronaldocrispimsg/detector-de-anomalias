"""Treino PEFT (LoRA) e carregamento do adaptador.

Sem treinar aqui: este módulo define o *spec* do adaptador, o guard de QLoRA e o
loader do provider (base + adaptador). Os imports pesados (torch, transformers,
peft, bitsandbytes) são tardios. QLoRA 4 bits exige Linux + CUDA + bitsandbytes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_TARGET_MODULES = ("q_proj", "k_proj", "v_proj", "o_proj")


@dataclass
class LoraSpec:
    r: int = 16
    alpha: int = 32
    dropout: float = 0.05
    target_modules: tuple[str, ...] = DEFAULT_TARGET_MODULES
    bias: str = "none"
    quant_4bit: bool = False
    lr: float = 2e-4
    epochs: int = 3
    batch_size: int = 4
    grad_accum: int = 4
    max_seq_len: int = 512
    early_stopping_patience: int = 2

    def __post_init__(self) -> None:
        if self.alpha != 2 * self.r:
            raise ValueError("alpha deve ser 2*r por convenção da fase")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["target_modules"] = list(self.target_modules)
        return data

    def to_lora_config(self):  # pragma: no cover - depende de peft
        from peft import LoraConfig

        return LoraConfig(
            r=self.r,
            lora_alpha=self.alpha,
            lora_dropout=self.dropout,
            target_modules=list(self.target_modules),
            bias=self.bias,
            task_type="CAUSAL_LM",
        )


def cuda_available() -> bool:
    try:
        import torch
    except ImportError:
        return False
    return bool(torch.cuda.is_available())


def qlora_supported() -> bool:
    """QLoRA 4 bits só é válido em Linux + CUDA com bitsandbytes."""
    if not cuda_available():
        return False
    try:
        import bitsandbytes  # noqa: F401
    except ImportError:
        return False
    return True


def load_base_model(spec: LoraSpec, model_name: str, *, device: str | None = None):
    """Carrega base (com quantização 4 bits se pedido). Import tardio."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if spec.quant_4bit and not qlora_supported():
        raise RuntimeError(
            "QLoRA 4 bits exige Linux + CUDA + bitsandbytes; use quant_4bit=False"
        )

    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    kwargs: dict[str, Any] = {}
    if spec.quant_4bit:
        from transformers import BitsAndBytesConfig

        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        kwargs["device_map"] = "auto"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name, **kwargs)
    if not spec.quant_4bit:
        model.to(device)
    return model, tokenizer, device


def train_lora(  # pragma: no cover - execução pesada, fora do pytest
    train_jsonl: str | Path,
    output_dir: str | Path,
    *,
    model_name: str,
    spec: LoraSpec,
) -> dict[str, Any]:
    """Fine-tune SFT com LoRA. Retorna métricas básicas do treino."""
    import torch
    from datasets import load_dataset
    from peft import get_peft_model
    from transformers import Trainer, TrainingArguments

    model, tokenizer, device = load_base_model(spec, model_name)
    model = get_peft_model(model, spec.to_lora_config())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)

    def _tokenize(example):
        text = tokenizer.apply_chat_template(
            example["messages"], tokenize=False, add_generation_prompt=False
        )
        enc = tokenizer(text, truncation=True, max_length=spec.max_seq_len)
        enc["labels"] = list(enc["input_ids"])
        return enc

    ds = load_dataset("json", data_files=str(train_jsonl), split="train")
    ds = ds.map(_tokenize, remove_columns=ds.column_names)

    args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=spec.epochs,
        per_device_train_batch_size=spec.batch_size,
        gradient_accumulation_steps=spec.grad_accum,
        learning_rate=spec.lr,
        logging_steps=10,
        save_strategy="epoch",
        bf16=torch.cuda.is_available(),
        report_to=[],
    )
    trainer = Trainer(model=model, args=args, train_dataset=ds)
    trainer.train()
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    return {
        "trainable_params": int(trainable),
        "device": device,
        "quant_4bit": spec.quant_4bit,
        "spec": spec.to_dict(),
    }


def load_peft_provider(
    base_model: str, adapter_dir: str | Path, **provider_kwargs: Any
):  # pragma: no cover - depende de peft
    """Carrega base + adaptador e devolve um `TorchProvider`-compatível."""
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    import torch

    from Backend.services.agent.models import TorchProvider

    provider = TorchProvider.__new__(TorchProvider)
    provider._torch = torch
    provider.model_name = base_model
    provider.id = f"peft:{base_model}+{Path(adapter_dir).name}"
    provider.max_new_tokens = provider_kwargs.get("max_new_tokens", 256)
    provider.temperature = provider_kwargs.get("temperature", 0.0)
    provider.device = provider_kwargs.get(
        "device", "cuda" if torch.cuda.is_available() else "cpu"
    )
    provider.tokenizer = AutoTokenizer.from_pretrained(base_model)
    base = AutoModelForCausalLM.from_pretrained(base_model)
    provider.model = PeftModel.from_pretrained(base, str(adapter_dir))
    provider.model.to(provider.device)
    provider.model.eval()
    return provider
