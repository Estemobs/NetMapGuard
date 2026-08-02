# Contribution

Merci de vouloir contribuer à NetMapGuard !

## Développement

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Vérifications avant PR

```bash
pytest tests/ -v
```

## Build d'un exécutable

```bash
pip install pyinstaller
pyinstaller netmapguard.spec
```

Un tag `vX.Y.Z` déclenche la CI qui compile les binaires Windows/macOS/Linux et publie la release.

## Licence

Ce projet est sous licence CC BY-NC-SA 4.0 (usage non commercial).
