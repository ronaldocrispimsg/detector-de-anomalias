# Backend Services Agent: Agente de Mitigação Autônoma em Ciclo Fechado

O diretório `Backend/services/agent/` implementa o agente autônomo com saída estritamente estruturada, validação de evidências e ciclo fechado de mitigação.

## Componentes

- `loop.py`: Ciclo autônomo de observação, decisão, remediação e verificação.
- `structured.py`: Esquema Pydantic para saídas tipadas e auditáveis.
- `grounding.py`: Checagem factual de que todas as evidências citadas pelo LLM constam na telemetria observada.
- `decision.py`: Lógica de calibração de confiança e abstenção automática quando incerteza > 30%.
- `tool_guard.py` & `tools.py`: Guardrails operacionais e ferramentas seguras de remediação de rede.
- `xai.py`: Explicabilidade das decisões tomadas para auditoria humana.
- `tests/`: Suíte completa de testes de contrato, anti-alucinação, ciclo fechado e vazamento de RAG.

## Execução dos Testes

```bash
pytest Backend/services/agent/tests -v
```
