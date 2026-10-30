#!/bin/sh
# Installs the three models that passed the reliability tests into ~/.fire-discoverer.
# Needs git, curl and cargo. Downloads about 390 MB; about 180 MB stays on disk.
set -e
HOME_DIR="$HOME/.fire-discoverer"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$HOME_DIR/bin"
OWNER=https://github.com/AlexandrosGiann

fetch() { # repo commit dir
  git clone -q "$OWNER/$1" "$WORK/$3"
  git -C "$WORK/$3" checkout -q "$2"
}

fetch Cactus_Whistle-Pure_Rust 79946b745da4284df26344bf9decabf7cc59cc4f whistle
(cd "$WORK/whistle" && cargo build --release -q)
cp "$WORK"/whistle/target/release/whistle* "$HOME_DIR/bin/"
curl -sSL --fail -o "$WORK/whistle.cact" https://huggingface.co/Cactus-Compute/whistle/resolve/main/whistle.cact
echo "b6e02f048568ac5d01a2042556c658061e699acbc0aa2a1439f52f3d461dffeb  $WORK/whistle.cact" | sha256sum -c --quiet -
mv "$WORK/whistle.cact" "$HOME_DIR/whistle.cact"

fetch paraphrase-multilingual-MiniLM-L12-v2_PureRust ddf2d9ac40a0e037b04d0d6e8661f62e2f0869b3 minilm
(cd "$WORK/minilm" && cargo build --release -q)
cp "$WORK"/minilm/target/release/minilm* "$HOME_DIR/bin/"
rm -rf "$HOME_DIR/minilm-model"
cp -r "$WORK/minilm/model" "$HOME_DIR/minilm-model"

fetch mobileclip-s0-purejs-oldandroid ade346b9f15b22744f2ea54b038d0a4aa72a821f mobileclip
fetch MobileCLIP-S0_PureRust 791db1271cfa15dd5d0a104dbd55a4acb7254975 mobileclip/rust
(cd "$WORK/mobileclip/rust" && cargo build --release -q)
cp "$WORK"/mobileclip/rust/target/release/mobileclip-s0* "$HOME_DIR/bin/"
rm -rf "$HOME_DIR/mobileclip"
mkdir "$HOME_DIR/mobileclip"
cp -r "$WORK/mobileclip/compiled-fp32-v1" "$WORK/mobileclip/text-bank" "$HOME_DIR/mobileclip/"

rm -f "$HOME_DIR"/bin/*.d "$HOME_DIR"/bin/*.pdb
"$HOME_DIR/bin/minilm" similarity --model "$HOME_DIR/minilm-model" "ok" "ok" >/dev/null
"$HOME_DIR/bin/mobileclip-s0" validate --root "$HOME_DIR/mobileclip" >/dev/null
echo "ok: $HOME_DIR"
