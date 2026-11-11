"""Cliente LLM simulado (compatible con la interfaz de openai) para probar el loop."""
from __future__ import annotations

import json
from types import SimpleNamespace as NS


def _tc(i, name, args):
    return NS(id=f"call_{i}", type="function",
              function=NS(name=name, arguments=json.dumps(args, ensure_ascii=False)))


class ScriptedClient:
    """Devuelve una secuencia fija de respuestas: listas de (tool, args) o texto final."""

    def __init__(self, script, fail_times: int = 0):
        self.script = list(script)
        self.fail_times = fail_times
        self.calls = []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        if self.fail_times > 0:
            self.fail_times -= 1
            raise ConnectionError("proveedor caído (simulado)")
        item = self.script.pop(0) if self.script else "Respuesta final [SIATA-DATOS]"
        if isinstance(item, str):
            msg = NS(content=item, tool_calls=None)
        else:
            msg = NS(content="", tool_calls=[_tc(i, n, a) for i, (n, a) in enumerate(item)])
        return NS(choices=[NS(message=msg)])
