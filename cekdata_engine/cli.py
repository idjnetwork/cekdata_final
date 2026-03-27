"""
cli.py
======
Entry point command-line interface untuk CekData Engine.

Pakai:
    python -m cekdata_engine.cli "Benarkah kemiskinan turun di Jawa Timur?"

Atau jika diinstall sebagai package:
    cekdata "Benarkah kemiskinan turun di Jawa Timur?"
"""
from __future__ import annotations

import json
import sys


def main() -> None:
    if len(sys.argv) < 2:
        print("Pakai: python -m cekdata_engine.cli \"pertanyaan\"", file=sys.stderr)
        raise SystemExit(1)

    question = " ".join(sys.argv[1:]).strip()
    if not question:
        print("Pertanyaan tidak boleh kosong.", file=sys.stderr)
        raise SystemExit(1)

    # Import lazy — engine tidak diinisialisasi sampai sini
    from cekdata_engine import answer_question

    result = answer_question(question)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
