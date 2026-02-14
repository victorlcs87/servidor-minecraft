#!/usr/bin/env python3
"""bedrock_addon_installer.py (TUI)

Gerenciador interativo de Addons (Behavior/Resource packs) para Bedrock Dedicated Server.

Conceitos:
- Installed = pack existe em behavior_packs/ ou resource_packs/.
- Active    = pack_id aparece em worlds/<mundo>/world_behavior_packs.json ou world_resource_packs.json.

Funcionalidades:
- Install: copiar packs (opcional) + registrar no mundo (merge seguro).
- Manage: visualizar Installed vs Active, com filtros, toggle e modo em lote.
- Remove: atalho para desativar um pack ativo.
- Relatório: worlds/<mundo>/world_packs_report.md (inclui status).

Segurança:
- Ao escrever world_*.json: cria backup .prewrite.bak.
- Se world_*.json estiver inválido: cria .invalid.bak e aborta.

Dependências:
- rich (interface colorida)
- InquirerPy (menus interativos)

Requisitos: Python 3.9+
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set
import zipfile
import tempfile
import glob


# -------------------------
# Rich Console (fallback to simple print if not available)
# -------------------------

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    console: Optional[Console] = Console()
except ImportError:
    console = None


def info(msg: str) -> None:
    if console:
        console.print(f"[cyan][ℹ][/cyan] {msg}")
    else:
        print(f"[i] {msg}")


def ok(msg: str) -> None:
    if console:
        console.print(f"[bold green][✓][/bold green] {msg}")
    else:
        print(f"[OK] {msg}")


def warn(msg: str) -> None:
    if console:
        console.print(f"[bold yellow][⚠][/bold yellow] {msg}")
    else:
        print(f"[!] {msg}")


def err(msg: str) -> None:
    if console:
        console.print(f"[bold red][✗][/bold red] {msg}")
    else:
        print(f"[x] {msg}")


def title(msg: str) -> None:
    if console:
        console.print()
        console.print(Panel(
            Text(msg, style="bold magenta", justify="center"),
            box=box.DOUBLE,
            border_style="bright_blue",
            padding=(0, 2)
        ))
        console.print()
    else:
        bar = "=" * 70
        print(bar)
        print(msg)
        print(bar)


def goodbye_msg() -> None:
    """Mensagem de saída quando usuário cancela com Ctrl+C."""
    if console:
        console.print()
        console.print(Panel(
            Text("👋 Até logo! Operação cancelada pelo usuário.", style="bold cyan", justify="center"),
            box=box.ROUNDED,
            border_style="dim",
            padding=(0, 2)
        ))
        console.print()
    else:
        print("\n[!] Operação cancelada pelo usuário. Até logo!")


def colorize_type(which: str) -> str:
    """Retorna o tipo do pack com cor apropriada."""
    if console:
        if which == "behavior":
            return "[bold orange3]behavior[/bold orange3]"
        elif which == "resource":
            return "[bold dodger_blue2]resource[/bold dodger_blue2]"
    return which


def colorize_status(is_active: bool) -> str:
    """Retorna o status com cor apropriada."""
    if console:
        if is_active:
            return "[bold green]ACTIVE[/bold green]"
        else:
            return "[dim]inactive[/dim]"
    return "ACTIVE" if is_active else "inactive"


def format_pack_label(p, is_active: bool) -> str:
    """Formata o label de um pack para exibição."""
    type_colored = colorize_type(p.which)
    status_colored = colorize_status(is_active)
    return f"[{type_colored}] {p.name}  - {status_colored}"


# -------------------------
# Dependency: InquirerPy
# -------------------------

def ensure_dependencies() -> None:
    """Verifica se as dependências estão instaladas."""
    missing = []
    
    try:
        import rich  # noqa: F401
    except ImportError:
        missing.append("rich")
    
    try:
        import InquirerPy  # noqa: F401
    except ImportError:
        missing.append("InquirerPy")
    
    if not missing:
        return
    
    deps = ", ".join(missing)
    print()
    print("=" * 60)
    print(f"DEPENDÊNCIAS NÃO ENCONTRADAS: {deps}")
    print("=" * 60)
    print()
    print("Instale manualmente usando uma das opções abaixo:")
    print()
    print("[!] Opção 1 - Instalação local (mais simples):")
    print(f"    pip install --user --break-system-packages {' '.join(missing)}")
    print()
    print("[!] Opção 2 - Virtual Environment (recomendado):")
    print("    python3 -m venv venv")
    print("    source venv/bin/activate")
    print(f"    pip install {' '.join(missing)}")
    print("    python3 bedrock_addon_installer.py")
    print()
    print("=" * 60)
    raise SystemExit(1)


def tui():
    ensure_dependencies()
    from InquirerPy import inquirer  # type: ignore
    from InquirerPy.validator import PathValidator  # type: ignore
    from InquirerPy.base import Choice  # type: ignore
    from InquirerPy.separator import Separator  # type: ignore

    return inquirer, PathValidator, Choice, Separator


# -------------------------
# Core logic
# -------------------------
@dataclass(frozen=True)
class PackRef:
    which: str      # 'behavior'|'resource'
    name: str       # folder name
    pack_id: str    # header.uuid
    version: List[int]


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def safe_backup(path: Path, suffix: str) -> Optional[Path]:
    if not path.exists():
        return None
    backup = path.with_suffix(path.suffix + suffix)
    shutil.copy2(path, backup)
    return backup


def ensure_manifest(pack_dir: Path, desired_type: str) -> Dict[str, Any]:
    manifest_path = pack_dir / "manifest.json"

    def make_new() -> Dict[str, Any]:
        module_type = "resources" if desired_type == "resource" else "data"
        return {
            "format_version": 2,
            "header": {
                "name": pack_dir.name,
                "description": f"{desired_type.capitalize()} pack for Bedrock Dedicated Server",
                "uuid": str(uuid.uuid4()),
                "version": [1, 0, 0],
                "min_engine_version": [1, 19, 0],
            },
            "modules": [
                {
                    "type": module_type,
                    "uuid": str(uuid.uuid4()),
                    "version": [1, 0, 0],
                }
            ],
        }

    manifest: Optional[Dict[str, Any]] = None
    if manifest_path.exists():
        try:
            m = load_json(manifest_path)
            manifest = m if isinstance(m, dict) else None
        except Exception:
            manifest = None

    if manifest is None:
        manifest = make_new()
        warn(f"manifest.json ausente/inválido em '{pack_dir.name}'. Criando um novo.")
    else:
        manifest.setdefault("format_version", 2)
        if not isinstance(manifest.get("header"), dict):
            manifest["header"] = {}
        header = manifest["header"]
        header.setdefault("name", pack_dir.name)
        header.setdefault("uuid", str(uuid.uuid4()))
        if not isinstance(header.get("version"), list):
            header["version"] = [1, 0, 0]
        header.setdefault("min_engine_version", [1, 19, 0])

        desc = header.get("description")
        if not isinstance(desc, str) or not desc.strip():
            header["description"] = f"{desired_type.capitalize()} pack for Bedrock Dedicated Server"
        else:
            if desired_type == "resource" and "behavior" in desc.lower():
                header["description"] = "Resource pack for Bedrock Dedicated Server"
            if desired_type == "behavior" and "resource" in desc.lower():
                header["description"] = "Behavior pack for Bedrock Dedicated Server"

        if not isinstance(manifest.get("modules"), list):
            manifest["modules"] = []

        correct_module_type = "resources" if desired_type == "resource" else "data"
        if len(manifest["modules"]) == 0:
            manifest["modules"].append({
                "type": correct_module_type,
                "uuid": str(uuid.uuid4()),
                "version": [1, 0, 0],
            })
        else:
            for mod in manifest["modules"]:
                if not isinstance(mod, dict):
                    continue
                if not mod.get("uuid"):
                    mod["uuid"] = str(uuid.uuid4())
                if not isinstance(mod.get("version"), list):
                    mod["version"] = [1, 0, 0]
                if mod.get("type") != correct_module_type:
                    mod["type"] = correct_module_type

    dump_json(manifest_path, manifest)
    return manifest


def pack_ref_from_manifest(manifest: Dict[str, Any], which: str, folder_name: str) -> PackRef:
    header = manifest.get("header") or {}
    pack_id = header.get("uuid")
    version = header.get("version")

    if not isinstance(pack_id, str) or not pack_id:
        raise ValueError("manifest header.uuid ausente/inválido")

    if not isinstance(version, list) or not all(isinstance(x, int) for x in version):
        version = [1, 0, 0]

    # Ensure strict list[int] for type checker
    if version is None:
        version = [1, 0, 0]
    version_int: List[int] = [int(x) for x in version]
    return PackRef(which=which, name=folder_name, pack_id=pack_id, version=version_int)


def iter_pack_dirs(source: Path) -> List[Path]:
    """Retorna a pasta do pack para instalação.
    
    Importante: sempre retorna a pasta fonte como o pack.
    O ensure_manifest criará o manifest.json se necessário.
    Não fragmenta o addon em subpastas.
    """
    # Sempre retorna a pasta fonte - ela É o pack
    # O ensure_manifest vai criar o manifest se não existir
    return [source]



def copy_pack_dir(src: Path, dst_root: Path) -> Path:
    dst = dst_root / src.name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


def read_world_list(server_dir: Path) -> List[str]:
    worlds_dir = server_dir / "worlds"
    if not worlds_dir.exists():
        return []
    return sorted([p.name for p in worlds_dir.iterdir() if p.is_dir()])


def choose_world(server_dir: Path, inquirer) -> Path:
    worlds = read_world_list(server_dir)
    if not worlds:
        raise RuntimeError("Nenhum mundo encontrado em worlds/")
    if len(worlds) == 1:
        ok(f"Apenas 1 mundo encontrado. Selecionado automaticamente: {worlds[0]}")
        return server_dir / "worlds" / worlds[0]

    choice = inquirer.select(
        message="Selecione o mundo:",
        choices=worlds,
        default=worlds[0],
    ).execute()
    return server_dir / "worlds" / choice


def world_json_path(world_dir: Path, which: str) -> Path:
    return world_dir / f"world_{which}_packs.json"


def load_active_ids(world_dir: Path) -> Any:
    out = {"behavior": set(), "resource": set()}
    for which in ("behavior", "resource"):
        path = world_json_path(world_dir, which)
        if not path.exists():
            continue
        data = load_json(path)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and isinstance(item.get("pack_id"), str):
                    out[which].add(item["pack_id"])
    return out


def update_world_json(world_dir: Path, which: str, new_refs: List[PackRef]) -> None:
    filename = f"world_{which}_packs.json"
    path = world_json_path(world_dir, which)

    existing: List[Dict[str, Any]] = []
    if path.exists():
        try:
            data = load_json(path)
            if not isinstance(data, list):
                raise ValueError("arquivo não é uma lista JSON")
            existing = data
        except Exception as e:
            bak = safe_backup(path, ".invalid.bak")
            raise RuntimeError(
                f"{filename} inválido ({e}). Backup criado em {bak}. Não vou sobrescrever."
            )

    seen = set()
    for item in existing:
        if isinstance(item, dict) and isinstance(item.get("pack_id"), str):
            seen.add(item["pack_id"])

    added = 0
    for ref in new_refs:
        if ref.pack_id not in seen:
            item: Dict[str, Any] = {"pack_id": ref.pack_id, "version": ref.version}
            existing.append(item)
            seen.add(ref.pack_id)
            added = added + 1

    safe_backup(path, ".prewrite.bak")
    dump_json(path, existing)
    ok(f"{filename}: adicionados {added}, total agora {len(existing)}")


def set_active(world_dir: Path, ref: PackRef, active: bool) -> None:
    path = world_json_path(world_dir, ref.which)
    filename = path.name

    data: List[Any] = []
    if path.exists():
        try:
            d = load_json(path)
            if not isinstance(d, list):
                raise ValueError("arquivo não é uma lista JSON")
            data = d
        except Exception as e:
            bak = safe_backup(path, ".invalid.bak")
            raise RuntimeError(f"{filename} inválido ({e}). Backup criado em {bak}. Não vou sobrescrever.")

    if active:
        seen = {item.get("pack_id") for item in data if isinstance(item, dict)}
        if ref.pack_id not in seen:
            data.append({"pack_id": ref.pack_id, "version": ref.version})
    else:
        data = [item for item in data if not (isinstance(item, dict) and item.get("pack_id") == ref.pack_id)]

    safe_backup(path, ".prewrite.bak")
    dump_json(path, data)


def scan_installed(server_dir: Path) -> List[PackRef]:
    installed: List[PackRef] = []
    for which, rootname in (("behavior", "behavior_packs"), ("resource", "resource_packs")):
        root = server_dir / rootname
        if not root.exists():
            continue
        
        # Pastas do sistema que não devem ser mexidas
        system_folders = {"vanilla", "chemistry", "premium_cache", "development_behavior_packs", "development_resource_packs"}
        
        for d in [p for p in root.iterdir() if p.is_dir()]:
            if d.name.lower() in system_folders or d.name.lower().startswith("chemistry"):
                continue
            m = ensure_manifest(d, which)
            installed.append(pack_ref_from_manifest(m, which, d.name))
    return installed


def write_world_packs_md(world_dir: Path, installed: List[PackRef], active_ids: Dict[str, set]) -> Path:
    out = world_dir / "world_packs_report.md"

    def mk_table(which: str) -> List[str]:
        rows: List[str] = []
        rows.append(f"## {which.capitalize()} packs")
        rows.append("")
        packs = [p for p in installed if p.which == which]
        if not packs:
            rows.append("(none)")
            rows.append("")
            return rows
        rows.append("| Status | Pack (folder) | UUID (pack_id) | Version |")
        rows.append("|---|---|---|---|")
        for p in sorted(packs, key=lambda x: x.name.lower()):
            st = "ACTIVE" if p.pack_id in active_ids[which] else "inactive"
            v = ".".join(str(x) for x in p.version)
            rows.append(f"| {st} | `{p.name}` | `{p.pack_id}` | `{v}` |")
        rows.append("")
        return rows

    lines: List[str] = []
    lines.append("# World packs report")
    lines.append("")
    lines.append(f"World: `{world_dir.name}`")
    lines.append("")
    lines.extend(mk_table("behavior"))
    lines.extend(mk_table("resource"))

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


# -------------------------
# TUI actions
# -------------------------

def pick_optional_dir(inquirer, PathValidator, label: str) -> Optional[Path]:
    use = inquirer.confirm(message=f"Deseja selecionar uma pasta de {label}?", default=False).execute()
    if not use:
        return None
    path_s = inquirer.filepath(
        message=f"Selecione a pasta de {label}:",
        only_directories=True,
        validate=PathValidator(is_dir=True, message="Selecione um diretório válido."),
    ).execute()
    return Path(path_s)


def run_install(server_dir: Path, world_dir: Path, behavior_src: Optional[Path], resource_src: Optional[Path]) -> None:
    behavior_refs: List[PackRef] = []
    resource_refs: List[PackRef] = []

    if behavior_src is not None:
        behavior_root = Path(server_dir) / "behavior_packs"
        behavior_root.mkdir(parents=True, exist_ok=True)
        info(f"Copiando Behavior Packs para: {behavior_root}")
        for p in iter_pack_dirs(behavior_src):
            ensure_manifest(p, "behavior")
            copied = copy_pack_dir(p, behavior_root)
            m2 = ensure_manifest(copied, "behavior")
            behavior_refs.append(pack_ref_from_manifest(m2, "behavior", copied.name))
        ok(f"Behavior Packs processados: {len(behavior_refs)}")

    if resource_src is not None:
        resource_root = Path(server_dir) / "resource_packs"
        resource_root.mkdir(parents=True, exist_ok=True)
        info(f"Copiando Resource Packs para: {resource_root}")
        for p in iter_pack_dirs(resource_src):
            ensure_manifest(p, "resource")
            copied = copy_pack_dir(p, resource_root)
            m2 = ensure_manifest(copied, "resource")
            resource_refs.append(pack_ref_from_manifest(m2, "resource", copied.name))
        ok(f"Resource Packs processados: {len(resource_refs)}")

    if not behavior_refs and not resource_refs:
        warn("Nenhum pack selecionado.")
        return

    if behavior_refs:
        update_world_json(world_dir, "behavior", behavior_refs)
    if resource_refs:
        update_world_json(world_dir, "resource", resource_refs)

    installed = scan_installed(server_dir)
    active = load_active_ids(world_dir)
    report = write_world_packs_md(world_dir, installed, active)
    ok(f"Relatório gerado/atualizado: {report}")


def find_all_bp_rp_folders(root_folder: Path, max_depth: int = 5) -> Tuple[List[Path], List[Path]]:
    """Busca recursiva por todas as pastas BP e RP dentro de uma pasta raiz.
    
    Retorna (lista_de_BP, lista_de_RP).
    Ignora pastas que são filhas de outras pastas BP/RP já encontradas.
    """
    behavior_paths: List[Path] = []
    resource_paths: List[Path] = []
    
    def is_bp_or_rp_name(name: str) -> Tuple[bool, bool]:
        """Retorna (is_bp, is_rp) baseado no nome."""
        name_lower = name.lower()
        
        # Behavior Pack variants
        is_bp = (
            "behavior" in name_lower 
            or name_lower.endswith(" bp") 
            or name_lower.endswith("_bp") 
            or name_lower == "bp"
            or " bp " in name_lower
        )
        
        # Resource Pack variants
        is_rp = (
            "resource" in name_lower 
            or name_lower.endswith(" rp") 
            or name_lower.endswith("_rp") 
            or name_lower == "rp"
            or " rp " in name_lower
        )
        
        return is_bp, is_rp
    
    def scan_recursive(folder: Path, depth: int) -> None:
        if depth > max_depth:
            return
        
        try:
            children = [item for item in folder.iterdir() if item.is_dir()]
            
            for item in children:
                is_bp, is_rp = is_bp_or_rp_name(item.name)
                
                if is_bp or is_rp:
                    # Verificar se a pasta contém subpastas que também são BP/RP.
                    # Se sim, é um container (ex: "Mythological Craft - BPv2.6.3"
                    # contendo subpastas BP e RP reais), não um pack final.
                    has_bp_rp_children = False
                    try:
                        for sub in item.iterdir():
                            if sub.is_dir():
                                sub_bp, sub_rp = is_bp_or_rp_name(sub.name)
                                if sub_bp or sub_rp:
                                    has_bp_rp_children = True
                                    break
                    except PermissionError:
                        pass
                    
                    if has_bp_rp_children:
                        # É um container - descer recursivamente
                        scan_recursive(item, depth + 1)
                    else:
                        # É o pack final
                        if is_bp:
                            behavior_paths.append(item)
                        elif is_rp:
                            resource_paths.append(item)
                else:
                    # Continuar buscando recursivamente
                    scan_recursive(item, depth + 1)
        except PermissionError:
            pass  # Ignorar pastas sem permissão
    
    scan_recursive(root_folder, 0)
    return behavior_paths, resource_paths


def run_install_from_addon_folder(server_dir: Path, world_dir: Path, addon_folder: Path) -> None:
    """Instala addon(s) a partir de uma pasta.
    
    Busca recursivamente por todas as pastas BP e RP dentro da pasta selecionada.
    """
    info(f"Buscando addons em: {addon_folder.name}")
    behavior_paths, resource_paths = find_all_bp_rp_folders(addon_folder)
    
    total_found = len(behavior_paths) + len(resource_paths)
    
    if total_found == 0:
        warn(f"Nenhuma pasta BP ou RP encontrada em: {addon_folder.name}")
        info("Dica: As pastas de addon devem ter 'BP' ou 'RP' no nome.")
        info("  Exemplos válidos: 'MeuAddon BP', 'MeuAddon_RP', 'Addon RP'")
        return
    
    info(f"Encontrados: {len(behavior_paths)} Behavior Pack(s), {len(resource_paths)} Resource Pack(s)")
    
    if behavior_paths:
        info("Behavior Packs:")
        for bp in sorted(behavior_paths, key=lambda x: x.name.lower()):
            info(f"  → {bp.name}")
    
    if resource_paths:
        info("Resource Packs:")
        for rp in sorted(resource_paths, key=lambda x: x.name.lower()):
            info(f"  → {rp.name}")
    
    # Instalar todos os packs encontrados
    all_behavior_refs: List[PackRef] = []
    all_resource_refs: List[PackRef] = []
    failed_installs: List[Tuple[str, str, str]] = []  # (nome, tipo, motivo)
    
    behavior_root = Path(server_dir) / "behavior_packs"
    resource_root = Path(server_dir) / "resource_packs"
    
    for bp in behavior_paths:
        try:
            behavior_root.mkdir(parents=True, exist_ok=True)
            for p in iter_pack_dirs(bp):
                ensure_manifest(p, "behavior")
                copied = copy_pack_dir(p, behavior_root)
                m2 = ensure_manifest(copied, "behavior")
                all_behavior_refs.append(pack_ref_from_manifest(m2, "behavior", copied.name))
        except Exception as e:
            failed_installs.append((bp.name, "behavior", str(e)))
    
    for rp in resource_paths:
        try:
            resource_root.mkdir(parents=True, exist_ok=True)
            for p in iter_pack_dirs(rp):
                ensure_manifest(p, "resource")
                copied = copy_pack_dir(p, resource_root)
                m2 = ensure_manifest(copied, "resource")
                all_resource_refs.append(pack_ref_from_manifest(m2, "resource", copied.name))
        except Exception as e:
            failed_installs.append((rp.name, "resource", str(e)))
    
    ok(f"Behavior Packs instalados: {len(all_behavior_refs)}")
    ok(f"Resource Packs instalados: {len(all_resource_refs)}")
    
    # Mostrar falhas, se houver
    if failed_installs:
        warn(f"Falhas na instalação: {len(failed_installs)}")
        for name, pack_type, reason in failed_installs:
            type_label = "🟠 BP" if pack_type == "behavior" else "🔵 RP"
            err(f"  [{type_label}] {name}")
            err(f"      Motivo: {reason}")
    
    if all_behavior_refs:
        update_world_json(world_dir, "behavior", all_behavior_refs)
    if all_resource_refs:
        update_world_json(world_dir, "resource", all_resource_refs)
    
    installed = scan_installed(server_dir)
    active = load_active_ids(world_dir)
    report = write_world_packs_md(world_dir, installed, active)
    ok(f"Relatório gerado/atualizado: {report}")
    
    # Resumo final
    if failed_installs:
        warn(f"⚠ Resumo: {len(all_behavior_refs) + len(all_resource_refs)} instalados, {len(failed_installs)} falharam")












def install_from_archive(server_dir: Path, world_dir: Path, archive_path: Path) -> None:
    """Instala addon a partir de um arquivo .zip/.mcpack/.mcaddon."""
    info(f"Processando arquivo: {archive_path.name}")
    
    # Usar uma pasta temporária dentro do diretório do servidor para evitar problemas de espaço no /tmp
    temp_extract_base = server_dir / ".tmp_addon_extract"
    temp_extract_base.mkdir(exist_ok=True)
    
    with tempfile.TemporaryDirectory(dir=temp_extract_base) as temp_dir:
        temp_path = Path(temp_dir)
        try:
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(temp_path)
            
            # Extração recursiva de mcpack/mcaddon internos
            def extract_recursive(folder: Path):
                found_archives = False
                for item in list(folder.rglob("*")):
                    if item.is_file() and item.suffix.lower() in [".mcpack", ".mcaddon", ".zip"]:
                        info(f"Extraindo arquivo interno: {item.name}")
                        # Cria pasta com mesmo nome (sem extensão) para extrair
                        target_dir = item.parent / item.stem
                        target_dir.mkdir(exist_ok=True)
                        try:
                            with zipfile.ZipFile(item, 'r') as z:
                                z.extractall(target_dir)
                            item.unlink() # Remove o arquivo original após extrair
                            found_archives = True
                        except Exception as e:
                            warn(f"Falha ao extrair {item.name}: {e}")
                
                # Se extraiu algo novo, varre novamente (pode ter zip dentro de zip)
                if found_archives:
                    extract_recursive(folder)

            extract_recursive(temp_path)

            # Reutiliza a lógica existente de instalação a partir de pasta
            run_install_from_addon_folder(server_dir, world_dir, temp_path)
            
        except zipfile.BadZipFile:
            err(f"Arquivo inválido ou corrompido: {archive_path.name}")
        except Exception as e:
            err(f"Erro ao processar arquivo: {e}")


def delete_pack(server_dir: Path, world_dir: Path, pack_ref: PackRef) -> None:
    """Remove um pack do JSON do mundo e deleta a pasta física."""
    
    # 1. Remover do JSON do mundo (desativar)
    set_active(world_dir, pack_ref, active=False)
    
    # 2. Deletar pasta física
    pack_path = server_dir / ("behavior_packs" if pack_ref.which == "behavior" else "resource_packs") / pack_ref.name
    
    if pack_path.exists():
        try:
            shutil.rmtree(pack_path)
            ok(f"Pasta deletada: {pack_path.name}")
        except Exception as e:
            err(f"Erro ao deletar pasta {pack_path.name}: {e}")
    else:
        warn(f"Pasta não encontrada (já deletada?): {pack_path.name}")


def _apply_filter(packs: List[PackRef], active: Dict[str, set], type_filter: str, status_filter: str, text: str) -> List[PackRef]:
    res = packs
    if type_filter in ("behavior", "resource"):
        res = [p for p in res if p.which == type_filter]

    if status_filter == "active":
        res = [p for p in res if p.pack_id in active[p.which]]
    elif status_filter == "inactive":
        res = [p for p in res if p.pack_id not in active[p.which]]

    if text:
        t = text.lower()
        res = [p for p in res if t in p.name.lower() or t in p.pack_id.lower()]

    return res


def _batch_set_active(world_dir: Path, installed_all: List[PackRef], selected: List[PackRef]) -> Tuple[int, int]:
    """Garante que exatamente os packs 'selected' (por tipo) fiquem ativos.

    Retorna (ativados, desativados).
    """
    active = load_active_ids(world_dir)
    selected_ids: Dict[str, Set[str]] = {"behavior": set(), "resource": set()}
    for p in selected:
        selected_ids[p.which].add(p.pack_id)

    cnt_a = 0
    cnt_d = 0
    
    for which in ("behavior", "resource"):
        current = set(active[which])
        target = set(selected_ids[which])

        to_enable = target - current
        to_disable = current - target

        # enable
        for pid in to_enable:
            ref = next((p for p in installed_all if p.which == which and p.pack_id == pid), None)
            if ref:
                set_active(world_dir, ref, active=True)
                cnt_a = cnt_a + 1

        # disable
        for pid in to_disable:
            ref = next((p for p in installed_all if p.which == which and p.pack_id == pid), None)
            if ref:
                set_active(world_dir, ref, active=False)
                cnt_d = cnt_d + 1

    return cnt_a, cnt_d


def manage_packs(server_dir: Path, world_dir: Path, inquirer, Choice, Separator) -> None:
    installed_all = scan_installed(server_dir)
    if not installed_all:
        warn("Nenhum pack instalado em behavior_packs/ ou resource_packs/.")
        return

    type_filter = "all"      # all|behavior|resource
    status_filter = "all"    # all|active|inactive
    text_filter = ""

    while True:
        active = load_active_ids(world_dir)
        filtered = _apply_filter(installed_all, active, type_filter, status_filter, text_filter)

        header = f"type={type_filter}, status={status_filter}" + (f", search='{text_filter}'" if text_filter else "")

        choices: List[Any] = []
        choices.append({"name": "⚙ Alterar filtros", "value": ("filters", None)})
        choices.append({"name": "☑ Ativar/Desativar em lote (checkbox)", "value": ("batch", None)})
        choices.append({"name": "📝 Atualizar report.md", "value": ("report", None)})
        choices.append({"name": "← Voltar", "value": ("back", None)})
        choices.append(Separator(f"─" * 12 + f" Filtros: {header} " + "─" * 12))

        if not filtered:
            choices.append({"name": "(nenhum pack com esses filtros)", "value": ("noop", None), "disabled": ""})
        else:
            for p in sorted(filtered, key=lambda x: (x.which, x.name.lower())):
                is_active = p.pack_id in active[p.which]
                type_label = "🟠 behavior" if p.which == "behavior" else "🔵 resource"
                st = "🟢 ACTIVE" if is_active else "🔴 inactive"
                choices.append({"name": f"[{type_label}] {p.name}  - {st}", "value": ("toggle", p)})

        sel_action, sel_pack = inquirer.select(message="Manage packs:", choices=choices).execute()

        if sel_action == "back":
            break

        if sel_action == "report":
            report = write_world_packs_md(world_dir, installed_all, active)
            ok(f"Relatório atualizado: {report}")
            continue

        if sel_action == "filters":
            type_filter = inquirer.select(
                message="Filtrar por tipo:",
                choices=[
                    {"name": "Todos", "value": "all"},
                    {"name": "Behavior", "value": "behavior"},
                    {"name": "Resource", "value": "resource"},
                ],
                default=type_filter,
            ).execute()

            status_filter = inquirer.select(
                message="Filtrar por status:",
                choices=[
                    {"name": "Todos", "value": "all"},
                    {"name": "Apenas ativos", "value": "active"},
                    {"name": "Apenas inativos", "value": "inactive"},
                ],
                default=status_filter,
            ).execute()

            text_filter = inquirer.text(
                message="Filtro de texto (nome/UUID) - vazio para limpar:",
                default=text_filter,
            ).execute().strip()
            continue

        if sel_action == "batch":
            # Checkbox: selecionar quais devem ficar ATIVOS (para o conjunto filtrado)
            if not filtered:
                warn("Nada para aplicar em lote com os filtros atuais.")
                continue

            # Preselect currently active within filtered
            # Usamos uma chave única (which:pack_id) como value para evitar problemas de serialização
            pack_lookup: Dict[str, PackRef] = {}
            cb_choices = []
            for p in sorted(filtered, key=lambda x: (x.which, x.name.lower())):
                enabled = p.pack_id in active[p.which]
                type_label = "🟠 behavior" if p.which == "behavior" else "🔵 resource"
                key = f"{p.which}:{p.pack_id}"
                pack_lookup[key] = p
                cb_choices.append(Choice(value=key, name=f"[{type_label}] {p.name}", enabled=enabled))

            selected_keys: List[str] = inquirer.checkbox(
                message="Marque os packs que devem ficar ATIVOS (os desmarcados serão desativados):",
                choices=cb_choices,
                instruction="(Espaço marca/desmarca, Enter confirma)",
            ).execute()

            confirm = inquirer.confirm(
                message=f"Aplicar mudanças em lote para {len(filtered)} packs filtrados?",
                default=False,
            ).execute()
            if not confirm:
                info("Cancelado.")
                continue

            # IMPORTANTE: aplicar lote apenas ao conjunto filtrado.
            # Para isso, vamos:
            # - Ativar os 'selected'
            # - Desativar os que estão ativos e não foram selecionados, mas somente dentro de 'filtered'
            activated_packs: List[PackRef] = []
            deactivated_packs: List[PackRef] = []
            filtered_ids = {"behavior": set(), "resource": set()}
            for p in filtered:
                filtered_ids[p.which].add(p.pack_id)

            selected_ids = {"behavior": set(), "resource": set()}
            for key in selected_keys:
                p: Optional[PackRef] = pack_lookup.get(key)
                if p:
                    selected_ids[p.which].add(p.pack_id)

            for which in ("behavior", "resource"):
                current = set(active[which]) & filtered_ids[which]
                target = set(selected_ids[which])

                to_enable = target - current
                to_disable = current - target

                for pid in to_enable:
                    ref = next((p for p in installed_all if p.which == which and p.pack_id == pid), None)
                    if ref:
                        set_active(world_dir, ref, active=True)
                        activated_packs.append(ref)

                for pid in to_disable:
                    ref = next((p for p in installed_all if p.which == which and p.pack_id == pid), None)
                    if ref:
                        set_active(world_dir, ref, active=False)
                        deactivated_packs.append(ref)

            # Mostrar detalhes das alterações
            if activated_packs:
                ok(f"Ativados ({len(activated_packs)}):")
                for p in sorted(activated_packs, key=lambda x: x.name.lower()):
                    type_label = "🟠 BP" if p.which == "behavior" else "🔵 RP"
                    ok(f"  [{type_label}] {p.name}")
            
            if deactivated_packs:
                warn(f"Desativados ({len(deactivated_packs)}):")
                for p in sorted(deactivated_packs, key=lambda x: x.name.lower()):
                    type_label = "🟠 BP" if p.which == "behavior" else "🔵 RP"
                    warn(f"  [{type_label}] {p.name}")
            
            if not activated_packs and not deactivated_packs:
                info("Nenhuma alteração realizada.")
            else:
                ok(f"Lote aplicado. Ativados: {len(activated_packs)}, Desativados: {len(deactivated_packs)}")
            
            report = write_world_packs_md(world_dir, installed_all, load_active_ids(world_dir))
            ok(f"Relatório atualizado: {report}")
            continue


        if sel_action == "toggle" and sel_pack is not None:
            # Explicit cast/assignment to avoid type checker confusion
            p: PackRef = sel_pack  # type: ignore
            is_active = p.pack_id in active[p.which]
            act = "Desativar" if is_active else "Ativar"
            type_label = "🟠 behavior" if p.which == "behavior" else "🔵 resource"
            confirm = inquirer.confirm(message=f"{act} [{type_label}] {p.name}?", default=False).execute()
            if not confirm:
                continue
            set_active(world_dir, p, active=(not is_active))
            ok(f"{act} OK: {p.name}")
            report = write_world_packs_md(world_dir, installed_all, load_active_ids(world_dir))
            ok(f"Relatório atualizado: {report}")
            continue


def remove_packs(server_dir: Path, world_dir: Path, inquirer, Choice, Separator) -> None:
    """Remove packs com filtros e seleção em lote."""
    installed_all = scan_installed(server_dir)
    if not installed_all:
        warn("Não há packs instalados para remover.")
        return

    type_filter = "all"
    status_filter = "all"
    text_filter = ""

    while True:
        active = load_active_ids(world_dir)
        filtered = _apply_filter(installed_all, active, type_filter, status_filter, text_filter)

        header = f"type={type_filter}, status={status_filter}" + (f", search='{text_filter}'" if text_filter else "")

        choices: List[Any] = []
        choices.append({"name": "⚙ Alterar filtros", "value": ("filters", None)})
        choices.append({"name": "🗑 Remover em lote (checkbox)", "value": ("batch", None)})
        choices.append({"name": "← Voltar", "value": ("back", None)})
        choices.append(Separator(f"─" * 12 + f" Filtros: {header} " + "─" * 12))

        if not filtered:
            choices.append({"name": "(nenhum pack com esses filtros)", "value": ("noop", None), "disabled": ""})
        else:
            for p in sorted(filtered, key=lambda x: (x.which, x.name.lower())):
                is_active = p.pack_id in active[p.which]
                type_label = "🟠 behavior" if p.which == "behavior" else "🔵 resource"
                st = "🟢 ATIVO" if is_active else "🔴 inativo"
                choices.append({"name": f"[{type_label}] {p.name} - {st}", "value": ("single", p)})

        sel_action, sel_pack = inquirer.select(message="Remove packs:", choices=choices).execute()

        if sel_action == "back":
            break

        if sel_action == "filters":
            type_filter = inquirer.select(
                message="Filtrar por tipo:",
                choices=[
                    {"name": "Todos", "value": "all"},
                    {"name": "Behavior", "value": "behavior"},
                    {"name": "Resource", "value": "resource"},
                ],
                default=type_filter,
            ).execute()

            status_filter = inquirer.select(
                message="Filtrar por status:",
                choices=[
                    {"name": "Todos", "value": "all"},
                    {"name": "Apenas ativos", "value": "active"},
                    {"name": "Apenas inativos", "value": "inactive"},
                ],
                default=status_filter,
            ).execute()

            text_filter = inquirer.text(
                message="Filtro de texto (nome/UUID) - vazio para limpar:",
                default=text_filter,
            ).execute().strip()
            continue

        if sel_action == "batch":
            if not filtered:
                warn("Nada para remover com os filtros atuais.")
                continue

            pack_lookup: Dict[str, PackRef] = {}
            cb_choices = []
            for p in sorted(filtered, key=lambda x: (x.which, x.name.lower())):
                type_label = "🟠 BP" if p.which == "behavior" else "🔵 RP"
                is_active = p.pack_id in active[p.which]
                status = "🟢" if is_active else "🔴"
                key = f"{p.which}:{p.pack_id}"
                pack_lookup[key] = p
                cb_choices.append(Choice(value=key, name=f"[{type_label}] {p.name} {status}", enabled=False))

            selected_keys: List[str] = inquirer.checkbox(
                message="Marque os packs para REMOVER (⚠ PERMANENTE!):",
                choices=cb_choices,
                instruction="(Espaço marca/desmarca, Enter confirma)",
            ).execute()

            if not selected_keys:
                info("Nenhum pack selecionado.")
                continue

            # Ensure explicit checking for dictionary keys
            selected_packs: List[PackRef] = []
            for k in selected_keys:
                if k in pack_lookup:
                    selected_packs.append(pack_lookup[str(k)])
            
            warn(f"⚠ ATENÇÃO: Você vai APAGAR PERMANENTEMENTE {len(selected_packs)} pack(s):")
            for p in selected_packs:
                type_label = "🟠 BP" if p.which == "behavior" else "🔵 RP"
                warn(f"  [{type_label}] {p.name}")

            confirm = inquirer.confirm(
                message=f"Confirma a REMOÇÃO COMPLETA de {len(selected_packs)} pack(s)?",
                default=False,
            ).execute()
            
            if not confirm:
                info("Cancelado.")
                continue

            # Remover cada pack
            removed_packs: List[PackRef] = []
            failed_removes: List[Tuple[str, str]] = []

            for ref in selected_packs:
                try:
                    # Desativar se ativo
                    if ref.pack_id in active[ref.which]:
                        set_active(world_dir, ref, active=False)
                    
                    # Apagar pasta
                    if ref.which == "behavior":
                        pack_path = Path(server_dir) / "behavior_packs" / ref.name
                    else:
                        pack_path = Path(server_dir) / "resource_packs" / ref.name
                    
                    if pack_path.exists():
                        shutil.rmtree(pack_path)
                    
                    removed_packs.append(ref)
                except Exception as e:
                    failed_removes.append((ref.name, str(e)))

            # Mostrar resultados
            if removed_packs:
                ok(f"Removidos ({len(removed_packs)}):")
                for p in removed_packs:
                    type_label = "🟠 BP" if p.which == "behavior" else "🔵 RP"
                    ok(f"  [{type_label}] {p.name}")

            if failed_removes:
                err(f"Falhas ({len(failed_removes)}):")
                for name, reason in failed_removes:
                    err(f"  {name}: {reason}")

            # Atualizar lista e relatório
            installed_all = scan_installed(server_dir)
            report = write_world_packs_md(world_dir, installed_all, load_active_ids(world_dir))
            ok(f"Relatório atualizado: {report}")
            ok(f"✅ {len(removed_packs)} pack(s) removido(s) completamente!")
            continue

        if sel_action == "single" and sel_pack is not None:
            ref: PackRef = sel_pack
            type_label = "🟠 BP" if ref.which == "behavior" else "🔵 RP"
            warn(f"⚠ ATENÇÃO: Isso vai APAGAR permanentemente [{type_label}] {ref.name}")
            confirm = inquirer.confirm(message=f"Confirma a REMOÇÃO COMPLETA?", default=False).execute()
            if not confirm:
                continue

            # Desativar se ativo
            if ref.pack_id in active[ref.which]:
                set_active(world_dir, ref, active=False)
                ok(f"Desativado: {ref.name}")

            # Apagar pasta
            if ref.which == "behavior":
                pack_path = Path(server_dir) / "behavior_packs" / ref.name
            else:
                pack_path = Path(server_dir) / "resource_packs" / ref.name

            if pack_path.exists():
                shutil.rmtree(pack_path)
                ok(f"Arquivos apagados: {pack_path}")

            installed_all = scan_installed(server_dir)
            report = write_world_packs_md(world_dir, installed_all, load_active_ids(world_dir))
            ok(f"Relatório atualizado: {report}")
            ok(f"✅ Pack '{ref.name}' removido!")
            continue





def detect_server_dirs(start_path: Path) -> List[Path]:
    """Detecta automaticamente diretórios de servidores Bedrock."""
    candidates: List[Path] = []
    
    # Lista de locais padrões para verificar
    search_paths = [
        Path("/var/opt/minecraft/crafty/crafty-4/servers"),  # Crafty default
        Path("/var/lib/pterodactyl/volumes"),                # Pterodactyl volumes (User requested)
        start_path / "servers",                              # Relative ./servers
        start_path,                                          # Current directory (single server?)
    ]

    for p in search_paths:
        if not p.exists() or not p.is_dir():
            continue

        # 1. É um servidor direto? (tem pasta worlds)
        if (p / "worlds").exists() and (p / "worlds").is_dir():
            if p not in candidates:
                candidates.append(p)
        else:
            # 2. É um container de servidores? (subpastas tem worlds)
            # Evita recursão profunda, olha apenas 1 nível
            try:
                for sub in p.iterdir():
                    if sub.is_dir() and (sub / "worlds").exists():
                        if sub not in candidates:
                            candidates.append(sub)
            except PermissionError:
                pass
                
    return candidates


def manage_delete(server_dir: Path, world_dir: Path, inquirer, Choice, Separator) -> None:
    """Menu para deletar packs."""
    installed_all = scan_installed(server_dir)
    if not installed_all:
        warn("Nenhum pack instalado para deletar.")
        return

    active = load_active_ids(world_dir)
    
    choices: List[Any] = []
    choices.append({"name": "← Voltar", "value": ("back", None)})
    choices.append(Separator("─" * 30))
    
    for p in sorted(installed_all, key=lambda x: (x.which, x.name.lower())):
        is_active = p.pack_id in active[p.which]
        type_label = "🟠 behavior" if p.which == "behavior" else "🔵 resource"
        st = "🟢 ACTIVE" if is_active else "🔴 inactive"
        # Mostra aviso se estiver ativo
        warning = " [EXISTE NO MUNDO]" if is_active else ""
        label = f"[{type_label}] {p.name} {st}{warning}"
        choices.append({"name": label, "value": ("delete", p)})

    sel_action, sel_pack = inquirer.select(
        message="Selecione o pack para DELETAR (Permanente):",
        choices=choices,
    ).execute()

    if sel_action == "back":
        return

    if sel_action == "delete" and sel_pack:
        if inquirer.confirm(message=f"Tem certeza que deseja DELETAR '{sel_pack.name}'? (Irreversível)", default=False).execute():
            delete_pack(server_dir, world_dir, sel_pack)
            # Recarrega menu
            manage_delete(server_dir, world_dir, inquirer, Choice, Separator)


# -------------------------
# Main
# -------------------------

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Bedrock Addon Installer")
    parser.add_argument("--auto-install", type=Path, help="Caminho para arquivo .zip/.mcpack para instalação automática (sem TUI)")
    parser.add_argument("--server-dir", type=Path, default=Path.cwd(), help="Pasta raiz do servidor")
    
    parser.add_argument("--auto-scan", action="store_true", help="Procura automaticamente por pastas addons_auto_install em todos os servidores detectados e instala os addons.")
    
    args = parser.parse_args()

    # Modo Auto-Scan (Procura em todos os servidores detectados)
    if args.auto_scan:
        title("Auto-Scan Addons Mode")
        detected = detect_server_dirs(Path.cwd())
        if not detected:
            print("[INFO] Nenhum servidor Bedrock detectado para scan.")
            return 0
        
        found_any = False
        for srv in detected:
            auto_dir = srv / "addons_auto_install"
            if auto_dir.exists() and auto_dir.is_dir():
                # Acha o mundo (primeiro disponível)
                worlds = read_world_list(srv)
                if not worlds:
                    continue
                
                world_dir = srv / "worlds" / worlds[0]
                
                # Procura por arquivos
                files = []
                for ext in ["*.zip", "*.mcpack", "*.mcaddon"]:
                    files.extend(list(auto_dir.glob(ext)))
                
                if not files:
                    continue
                
                found_any = True
                print(f"\n[Server] {srv.name} ({srv})")
                print(f"[World]  {world_dir.name}")
                
                processed_dir = auto_dir / "processed"
                processed_dir.mkdir(exist_ok=True)
                
                for f in files:
                    print(f"[Auto-Install] Instalando: {f.name}")
                    try:
                        install_from_archive(srv, world_dir, f)
                        # Move para processados
                        shutil.move(str(f), str(processed_dir / f.name))
                        ok(f"Sucesso: {f.name}")
                    except Exception as e:
                        err(f"Falha ao instalar {f.name}: {e}")
        
        if not found_any:
            print("[INFO] Nenhum novo addon encontrado nas pastas addons_auto_install.")
        return 0

    # Modo CLI (Auto-Install específico para um arquivo)
    if args.auto_install:
        if not args.auto_install.exists():
            print(f"[ERROR] Arquivo não encontrado: {args.auto_install}")
            return 1
            
        server_dir = args.server_dir
        if not server_dir.exists():
             # Tenta achar diretório atual se o default falhar
             server_dir = Path.cwd()

        # Tenta achar o mundo automaticamente (pega o primeiro)
        # Em auto-install, assumimos que há apenas 1 mundo ou o usuário quer o primeiro.
        worlds = read_world_list(server_dir)
        if not worlds:
            print("[ERROR] Nenhum mundo encontrado em worlds/")
            return 1
        
        world_dir = server_dir / "worlds" / worlds[0]
        print(f"[INFO] Auto-installing no mundo: {world_dir.name}")
        
        install_from_archive(server_dir, world_dir, args.auto_install)
        return 0

    # Modo TUI
    inquirer, PathValidator, Choice, Separator = tui()

    title("Bedrock Addon Installer (TUI) - v3.7")

    action = inquirer.select(
        message="O que você quer fazer?",
        choices=[
            {"name": "Install Addon (pasta com RP/BP)", "value": "install_addon"},
            {"name": "Install ZIP/mcaddon (arquivo)", "value": "install_zip"},
            {"name": "Install Manual (selecionar pastas separadas)", "value": "install"},
            {"name": "Manage (ativar/desativar + filtros + lote)", "value": "manage"},
            {"name": "Remove (desativar + apagar pack)", "value": "remove"},
            {"name": "Sair", "value": "exit"},
        ],
        default="manage",
    ).execute()

    if action == "exit":
        info("Saindo.")
        return 0

    # Server dir detection
    detected_servers = detect_server_dirs(Path.cwd())
    
    if not detected_servers:
        # Fallback to manual entry
        info("Nenhum servidor detectado automaticamente.")
        default = str(Path.cwd())
        server_s = inquirer.filepath(
            message="Selecione a pasta do servidor Bedrock (contém worlds/):",
            default=default,
            only_directories=True,
            validate=PathValidator(is_dir=True, message="Selecione um diretório válido."),
        ).execute()
        server_dir = Path(server_s)
    elif len(detected_servers) == 1:
        server_dir = detected_servers[0]
        # Confirmação rápida se não for óbvio
        if not inquirer.confirm(message=f"Usar servidor detectado: {server_dir}?", default=True).execute():
             # Fallback manual
            server_s = inquirer.filepath(
                message="Selecione a pasta do servidor Bedrock:",
                default=str(Path.cwd()),
                only_directories=True,
                validate=PathValidator(is_dir=True),
            ).execute()
            server_dir = Path(server_s)
    else:
        # Multiplos encontrados, pedir seleção
        choices_srv = []
        for d in detected_servers:
            choices_srv.append(Choice(value=d, name=f"{d.name} ({d})"))
        choices_srv.append(Choice(value=None, name="Outro (selecionar manualmente)"))
        
        sel = inquirer.select(
            message=f"Servidores detectados ({len(detected_servers)}):",
            choices=choices_srv,
        ).execute()
        
        if sel is None:
             server_s = inquirer.filepath(
                message="Selecione a pasta do servidor Bedrock:",
                default=str(Path.cwd()),
                only_directories=True,
                validate=PathValidator(is_dir=True),
            ).execute()
             server_dir = Path(server_s)
        else:
            server_dir = sel

    try:
        world_dir = choose_world(server_dir, inquirer)
    except Exception as e:
        err(str(e))
        return 1

    ok(f"Mundo selecionado: {world_dir.name}")

    try:
        if action == "install_addon":
            addon_folder = Path(inquirer.filepath(
                message="Selecione a pasta do addon (contendo subpastas RP/BP):",
                only_directories=True,
                validate=PathValidator(is_dir=True, message="Selecione um diretório válido."),
            ).execute())
            run_install_from_addon_folder(server_dir, world_dir, addon_folder)

        elif action == "install_zip":
            archive_path = Path(inquirer.filepath(
                message="Selecione o arquivo .zip/.mcpack/.mcaddon:",
                only_directories=False,
                validate=PathValidator(is_file=True, message="Selecione um arquivo válido."),
            ).execute())
            install_from_archive(server_dir, world_dir, archive_path)

        elif action == "install":
            behavior_src = None
            resource_src = None
            if inquirer.confirm(message="Selecionar uma pasta de Behavior Packs para copiar?", default=False).execute():
                behavior_src = Path(inquirer.filepath(message="Pasta de Behavior Packs:", only_directories=True, validate=PathValidator(is_dir=True)).execute())
            if inquirer.confirm(message="Selecionar uma pasta de Resource Packs para copiar?", default=False).execute():
                resource_src = Path(inquirer.filepath(message="Pasta de Resource Packs:", only_directories=True, validate=PathValidator(is_dir=True)).execute())
            run_install(server_dir, world_dir, behavior_src, resource_src)

        elif action == "manage":
            manage_packs(server_dir, world_dir, inquirer, Choice, Separator)

        elif action == "remove":
            # Agora "remove" apenas desativa. "Delete" remove arquivos.
            remove_packs(server_dir, world_dir, inquirer, Choice, Separator)

        elif action == "delete":
             # Menu para deletar fisicamente
            manage_delete(server_dir, world_dir, inquirer, Choice, Separator)

        else:
            err("Ação desconhecida.")
            return 1

        info("Dica: reinicie o servidor Bedrock para aplicar.")
        return 0

    except Exception as e:
        err(f"Erro: {e}")
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        goodbye_msg()
        raise SystemExit(130)
