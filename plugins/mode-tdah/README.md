# mode-tdah

Version 100 % française de [i-have-adhd](https://github.com/ayghri/i-have-adhd) : un plugin Claude Code qui façonne les réponses pour un lecteur TDAH (action suivante d'abord, étapes numérotées, pas de digressions, durées précises, victoires visibles).

Les fichiers d'origine du dépôt ne sont pas modifiés (sauf `.claude-plugin/marketplace.json`) : tout ce qui est français vit dans `plugins/mode-tdah/`.

## Installation (Claude Code)

```
/plugin marketplace add chetana/mode-tdah
/plugin install mode-tdah@mode-tdah
```

Le skill s'invoque avec `/mode-tdah` et reste actif jusqu'à « stop adhd mode » ou « mode normal ».

## Mode permanent

Pour injecter les règles à chaque début de session :

```
touch ~/.claude/.mode-tdah-always
```

Pour le désactiver définitivement : `rm ~/.claude/.mode-tdah-always`. Ce drapeau est distinct de `~/.claude/.i-have-adhd-always` (plugin d'origine) : les deux plugins ne se gênent pas.

## Cline

```
plugins/mode-tdah/install-cline.sh              # ~/.cline/rules/30-mode-tdah.md
plugins/mode-tdah/install-cline.sh --project    # ./.clinerules/mode-tdah.md
plugins/mode-tdah/install-cline.sh --uninstall  # retire uniquement ce fichier
```

Le script génère la règle à partir du `SKILL.md` sans frontmatter, est idempotent et ne touche à aucun autre fichier. Relancer après chaque mise à jour du skill.

## Suivre l'amont

```
git fetch upstream && git merge upstream/main
```

Les fichiers d'origine n'étant pas modifiés, la fusion se fait sans conflit (hors `marketplace.json`, voir ci-dessous). Ensuite, comparer `skills/i-have-adhd/SKILL.md` à `plugins/mode-tdah/skills/mode-tdah/SKILL.md` et reporter les changements dans la traduction.

Seul `.claude-plugin/marketplace.json` diffère de l'original : en cas de conflit, garder la version `mode-tdah`.

## Tests

```
python3 -m unittest discover -s tests -p 'test_*.py'
```

## Licence et attribution

MIT, voir `LICENSE` à la racine. Projet original : Ayoub G. ([@ayghri](https://github.com/ayghri)). Cette version n'est qu'une traduction et un packaging français.
