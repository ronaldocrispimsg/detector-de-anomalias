PY := .venv/bin/python

.PHONY: test repro repro-smoke repro-anomaly repro-report

test:
	$(PY) -m pytest Backend/harness/tests Backend/services/agent/tests -q

repro:
	$(PY) -m Backend.harness.repro --full

repro-smoke:
	$(PY) -m Backend.harness.repro --smoke

repro-anomaly:
	$(PY) -m Backend.harness.kathara.repro_anomaly

repro-report:
	$(PY) scripts/make_report_html.py
