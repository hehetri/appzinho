"""Tkinter-based editor for `items.bin` files.

This version restructures the code to avoid variable shadowing bugs such as
`'function' object has no attribute 'read'` that happened when helper
functions reused the same name as the file handle.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Dict, List
import builtins

# ============================================================
# Constantes e utilitários
# ============================================================

MEMSIZE = 236
ENCODING = "ISO-8859-1"


def get_int(byte_string: bytes) -> int:
    return int.from_bytes(byte_string, byteorder="little")


def to_bytes(value: int, length: int = 4) -> bytes:
    return int(value).to_bytes(length, byteorder="little")


def removenullbyte(value: bytes) -> str:
    return value.split(b"\x00")[0].decode(ENCODING)


def pad_string(value: str, length: int = 31) -> bytes:
    encoded = value.encode(ENCODING)
    return encoded + b"\x00" * (length - len(encoded))


def _sync_buyable_digit(item: Dict[str, object]) -> None:
    """Atualiza o 7º dígito do ID para refletir o campo ``buyable``.

    O binário original codifica se o item está disponível na loja no dígito na
    posição 7 (índice 6) do ID para bots (prefixos 11, 12 ou 13). Para que a
    edição de "Disponível na loja (0/1)" seja persistida no arquivo, precisamos
    reescrever esse dígito conforme o valor informado no formulário.
    """

    s_id = list(str(item["id"]))
    if len(s_id) < 7:
        return

    try:
        bot = int(item.get("bot", 0))
        buyable = int(item.get("buyable", 0))
    except (TypeError, ValueError):
        return

    if bot not in (1, 2, 3):
        return

    s_id[6] = "0" if buyable else "1"
    item["id"] = int("".join(s_id))


# ============================================================
# Carregar itens do arquivo BIN
# ============================================================


def parse_stats(block: bytes) -> Dict[str, int]:
    """Extrai a seção de estatísticas do bloco do item."""
    offsets = {
        "hpp": (58, 62),
        "attmin": (62, 66),
        "attmax": (66, 70),
        "atttransmin": (70, 74),
        "atttransmax": (74, 78),
        "transgauge": (78, 82),
        "crit": (82, 86),
        "evade": (86, 90),
        "spectrans": (90, 94),
        "speed": (94, 98),
        "transbotdef": (98, 102),
        "transbotatt": (102, 106),
        "transspeed": (106, 110),
        "rangeatt": (110, 114),
        "luk": (114, 118),
    }

    return {name: get_int(block[start:end]) for name, (start, end) in offsets.items()}


def load_items(bin_path: str = "items.bin") -> List[Dict[str, object]]:
    """Lê todos os itens do arquivo binário.

    A função evita sobrescrever o handle de arquivo, garantindo que chamadas a
    `.read()` continuem funcionando.
    """
    items: List[Dict[str, object]] = []

    try:
        with builtins.open(bin_path, "rb") as bin_file:
            bin_file.read(4)  # ignorar header

            while True:
                block = bin_file.read(MEMSIZE)
                if len(block) < MEMSIZE:
                    break

                item: Dict[str, object] = {
                    "id": get_int(block[0:4]),
                    "name": removenullbyte(block[4:35]),
                    "level": block[35],
                    "buy": get_int(block[37:41]),
                    "coins": get_int(block[41:45]),
                    "sell": get_int(block[45:49]),
                    "days": get_int(block[56:58]),
                    "stats": parse_stats(block),
                }

                s_id = str(item["id"])
                item["bot"] = 0
                item["part"] = 0
                item["buyable"] = 0

                if s_id.startswith("11"):
                    item["bot"] = 1
                    item["part"] = int(s_id[2])
                    if s_id[6] == "0":
                        item["buyable"] = 1
                elif s_id.startswith("12"):
                    item["bot"] = 2
                    item["part"] = int(s_id[2])
                    if s_id[6] == "0":
                        item["buyable"] = 1
                elif s_id.startswith("13"):
                    item["bot"] = 3
                    item["part"] = int(s_id[2])
                    if s_id[6] == "0":
                        item["buyable"] = 1

                items.append(item)

    except FileNotFoundError:
        messagebox.showerror("Erro", f"Arquivo {bin_path} não encontrado!")
    except Exception as exc:  # pragma: no cover - erros exibidos via messagebox
        messagebox.showerror("Erro", str(exc))

    return items


# ============================================================
# GUI DO EDITOR
# ============================================================


NUMERIC_FIELDS = {"id", "level", "buy", "sell", "coins", "days", "bot", "part", "buyable"}


class ItemEditor:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Bout Evolution - Item Editor (BIN)")
        self.root.geometry("950x600")

        self.items = load_items()
        self.current_item: Dict[str, object] | None = None

        # ---------------- LISTA (ESQUERDA) ----------------
        left = tk.Frame(root, padx=10, pady=10)
        left.pack(side="left", fill="y")

        tk.Label(left, text="Buscar item:").pack()

        self.search_var = tk.StringVar()
        search = tk.Entry(left, textvariable=self.search_var)
        search.pack()
        search.bind("<KeyRelease>", self.update_list)

        self.listbox = tk.Listbox(left, width=40, height=30)
        self.listbox.pack()
        self.listbox.bind("<<ListboxSelect>>", self.load_editor_fields)

        # ---------------- PAINEL DE EDIÇÃO (DIREITA) ----------------
        right = tk.Frame(root, padx=20, pady=20)
        right.pack(side="right", fill="both", expand=True)

        self.fields: Dict[str, tk.Entry] = {}

        labels = [
            ("ID", "id"),
            ("Nome", "name"),
            ("Level", "level"),
            ("Buy", "buy"),
            ("Sell", "sell"),
            ("Coins", "coins"),
            ("Dias", "days"),
            ("Bot", "bot"),
            ("Part", "part"),
            ("Disponível na loja (0/1)", "buyable"),
        ]

        row = 0
        for lbl, key in labels:
            tk.Label(right, text=lbl).grid(row=row, column=0, sticky="w")
            entry = tk.Entry(right)
            entry.grid(row=row, column=1)
            self.fields[key] = entry
            row += 1

        tk.Label(right, text="--- Estatísticas ---").grid(row=row, column=0, pady=10)
        row += 1

        self.stats_fields: Dict[str, tk.Entry] = {}
        stats = [
            "hpp",
            "attmin",
            "attmax",
            "atttransmin",
            "atttransmax",
            "transgauge",
            "crit",
            "evade",
            "spectrans",
            "speed",
            "transbotdef",
            "transbotatt",
            "transspeed",
            "rangeatt",
            "luk",
        ]

        for stat in stats:
            tk.Label(right, text=stat).grid(row=row, column=0, sticky="w")
            entry = tk.Entry(right)
            entry.grid(row=row, column=1)
            self.stats_fields[stat] = entry
            row += 1

        # Botões
        tk.Button(right, text="Salvar alterações", command=self.save_item_changes).grid(row=row, column=0, pady=20)
        tk.Button(right, text="Salvar items.bin", command=self.save_bin).grid(row=row, column=1, pady=20)

        self.update_list()

    # ------------------------------------------------------
    def update_list(self, event=None):
        search = self.search_var.get().lower()
        self.listbox.delete(0, tk.END)

        for item in self.items:
            if search in str(item.get("name", "")).lower():
                self.listbox.insert(tk.END, f"{item['id']} - {item['name']}")

    # ------------------------------------------------------
    def load_editor_fields(self, event=None):
        if not self.listbox.curselection():
            return

        selected = self.listbox.get(self.listbox.curselection()[0])
        item_id = int(selected.split(" - ")[0])
        item = next(i for i in self.items if i["id"] == item_id)
        self.current_item = item

        for key, entry in self.fields.items():
            entry.delete(0, tk.END)
            entry.insert(0, item.get(key, ""))

        for key, entry in self.stats_fields.items():
            entry.delete(0, tk.END)
            entry.insert(0, item["stats"].get(key, 0))

    # ------------------------------------------------------
    def _extract_form_values(self) -> Dict[str, object] | None:
        """Lê os campos da tela e converte para um dicionário pronto para salvar.

        Retorna ``None`` se algum campo numérico tiver um valor inválido, exibindo
        um alerta para o usuário.
        """

        data: Dict[str, object] = {"stats": {}}

        try:
            for key, entry in self.fields.items():
                value = entry.get()
                if key in NUMERIC_FIELDS:
                    data[key] = int(value) if value else 0
                else:
                    data[key] = value

            for key, entry in self.stats_fields.items():
                value = entry.get()
                data["stats"][key] = int(value) if value else 0

        except ValueError as exc:
            messagebox.showerror(
                "Erro de validação",
                f"Campo numérico inválido: {exc}\nVerifique os valores digitados.",
            )
            return None

        return data

    def _apply_form_to_current(self) -> bool:
        """Aplica as alterações do formulário no item selecionado.

        Retorna ``True`` quando a aplicação foi bem-sucedida. Se não houver item
        selecionado ou ocorrer erro de validação, exibe uma mensagem e retorna
        ``False``. Essa função centraliza a lógica para evitar que alterações em
        memória deixem de ser gravadas ao salvar o ``items.bin``.
        """

        if not self.current_item:
            messagebox.showwarning("Atenção", "Selecione um item primeiro.")
            return False

        updated = self._extract_form_values()
        if not updated:
            return False

        for key, value in updated.items():
            if key == "stats":
                self.current_item[key].update(value)
            else:
                self.current_item[key] = value

        _sync_buyable_digit(self.current_item)

        return True

    def save_item_changes(self):
        """Aplica as alterações do formulário ao item atualmente selecionado."""
        if self._apply_form_to_current():
            messagebox.showinfo("OK", "Alterações aplicadas!")

    # ------------------------------------------------------
    def save_bin(self):
        """Salva o arquivo ``items.bin`` com as alterações aplicadas."""
        if not self.items:
            messagebox.showwarning("Atenção", "Nenhum item carregado para salvar.")
            return

        # Garante que o item selecionado tenha as últimas edições antes de salvar
        if self.current_item:
            if not self._apply_form_to_current():
                return

        with builtins.open("items.bin", "wb") as bin_file:
            bin_file.write(b"\x00\x00\x00\x00")  # header original

            for item in self.items:
                block = bytearray(MEMSIZE)

                block[0:4] = to_bytes(item["id"])
                block[4:35] = pad_string(str(item["name"]))
                block[35] = int(item["level"])

                block[37:41] = to_bytes(item["buy"])
                block[41:45] = to_bytes(item["coins"])
                block[45:49] = to_bytes(item["sell"])

                block[56:58] = to_bytes(item["days"], 2)

                stats = item["stats"]
                offsets = {
                    "hpp": 58,
                    "attmin": 62,
                    "attmax": 66,
                    "atttransmin": 70,
                    "atttransmax": 74,
                    "transgauge": 78,
                    "crit": 82,
                    "evade": 86,
                    "spectrans": 90,
                    "speed": 94,
                    "transbotdef": 98,
                    "transbotatt": 102,
                    "transspeed": 106,
                    "rangeatt": 110,
                    "luk": 114,
                }

                for key, start in offsets.items():
                    block[start : start + 4] = to_bytes(int(stats[key]))

                bin_file.write(block)

        messagebox.showinfo("Sucesso!", "Arquivo items.bin salvo!")


# ============================================================
# EXECUTAR A APLICAÇÃO
# ============================================================


if __name__ == "__main__":
    root = tk.Tk()
    app = ItemEditor(root)
    root.mainloop()
