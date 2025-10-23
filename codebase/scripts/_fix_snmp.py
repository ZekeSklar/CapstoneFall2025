from pathlib import Path
path = Path("tickets/snmp_client.py")
text = path.read_text()
text = text.replace("    error_state_raw = models.CharField", "dummy")
