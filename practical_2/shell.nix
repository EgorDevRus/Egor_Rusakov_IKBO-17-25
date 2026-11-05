{ pkgs ? import <nixpkgs> { } }:

pkgs.mkShell {
  name = "cargo-deps-graph";

  packages = with pkgs; [
    python3
    graphviz
    cargo
    rustc
  ];

  shellHook = ''
    export PYTHONPATH="$PWD/src:$PYTHONPATH"
    echo "cargo-deps-graph: Python $(python3 --version | cut -d' ' -f2)"
  '';
}
