#!/usr/bin/env sh
# Installe le mode-tdah comme règle Cline (généré depuis skills/mode-tdah/SKILL.md, sans frontmatter).
#   install-cline.sh              -> $HOME/.cline/rules/30-mode-tdah.md (global)
#   install-cline.sh --project    -> ./.clinerules/mode-tdah.md (projet courant)
#   install-cline.sh --uninstall  -> supprime uniquement ce fichier (combinable avec --project)
# Idempotent. Ne touche jamais aux autres fichiers du dossier de règles.
set -eu

mode=install
scope=global
for arg in "$@"; do
  case "$arg" in
    --uninstall) mode=uninstall ;;
    --project) scope=project ;;
    -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
    *) echo "Option inconnue : $arg" >&2; exit 2 ;;
  esac
done

if [ "$scope" = project ]; then
  target_dir="$PWD/.clinerules"
  target="$target_dir/mode-tdah.md"
else
  [ -n "${HOME:-}" ] || { echo "HOME non défini" >&2; exit 1; }
  target_dir="$HOME/.cline/rules"
  target="$target_dir/30-mode-tdah.md"
fi

if [ "$mode" = uninstall ]; then
  if [ -f "$target" ]; then rm -- "$target"; echo "Supprimé : $target"; else echo "Rien à supprimer : $target"; fi
  exit 0
fi

script_dir=$(cd -- "$(dirname -- "$0")" && pwd)
skill="$script_dir/skills/mode-tdah/SKILL.md"
[ -f "$skill" ] || { echo "SKILL.md introuvable : $skill" >&2; exit 1; }

# Retire le frontmatter YAML de tête (uniquement s'il est refermé).
body=$(awk '
  NR == FNR {
    if (NR == 1 && $0 ~ /^---[[:space:]]*$/) { in_fm = 1; next }
    if (in_fm && $0 ~ /^---[[:space:]]*$/)   { in_fm = 0; closed = 1 }
    next
  }
  FNR == 1 { strip = closed }
  strip && FNR == 1 && $0 ~ /^---[[:space:]]*$/ { skipping = 1; next }
  skipping && $0 ~ /^---[[:space:]]*$/          { skipping = 0; next }
  !skipping { print }
' "$skill" "$skill")

mkdir -p "$target_dir"
tmp=$(mktemp "$target_dir/.mode-tdah.XXXXXX")
trap 'rm -f "$tmp"' EXIT
printf '<!-- Généré par plugins/mode-tdah/install-cline.sh : ne pas éditer, relancer le script. -->\n# MODE TDAH ACTIF (permanent)\n\nLes règles ci-dessous s'\''appliquent à chaque réponse. « stop adhd mode » ou « mode normal » les désactive.\n\n%s\n' "$body" > "$tmp"
chmod 644 "$tmp"
mv -- "$tmp" "$target"
trap - EXIT
echo "Installé : $target"
