import tkinter as tk
from tkinter import filedialog, messagebox
import struct

# O shop_decoded.bin possui um cabeçalho fixo de 48 bytes seguido por
# registros de 0x6C (108) bytes com os dados de cada item.
HEADER_SIZE = 48
ITEM_SIZE = 0x6C

# Offsets dentro de cada registro
NAME_OFFSET = 0x00
NAME_SIZE = 32
CATEGORY_OFFSET = 0x54  # valor de 4 bytes (ex.: 0x00010000 / 0x00020000)
BUYABLE_OFFSET = 0x50   # 1 byte (0 ou 0x71 nos dumps atuais)
ID_OFFSET = 0x5C        # identificador/índice do item


# -------------------------------
# Função para ler um item
# -------------------------------
def parse_item(data, offset):
    block = bytearray(data[offset:offset + ITEM_SIZE])

    name_raw = block[NAME_OFFSET:NAME_OFFSET + NAME_SIZE]
    name = name_raw.split(b"\x00")[0].decode("ascii", errors="ignore")

    item_id = struct.unpack("<I", block[ID_OFFSET:ID_OFFSET + 4])[0]
    category = struct.unpack("<I", block[CATEGORY_OFFSET:CATEGORY_OFFSET + 4])[0]
    buy_flag = block[BUYABLE_OFFSET]

    return {
        "offset": offset,
        "id": item_id,
        "name": name,
        "category": category,
        "buyable": buy_flag,
        "block": block,
    }


# -------------------------------
# Função para reconstruir itens
# -------------------------------
def rebuild_item(item):
    block = bytearray(item["block"])

    # nome
    name_bytes = item["name"].encode("ascii", errors="ignore")
    name_bytes = name_bytes[: NAME_SIZE - 1] + b"\x00"
    block[NAME_OFFSET:NAME_OFFSET + NAME_SIZE] = b"\x00" * NAME_SIZE
    block[NAME_OFFSET:NAME_OFFSET + len(name_bytes)] = name_bytes

    # categoria
    block[CATEGORY_OFFSET:CATEGORY_OFFSET + 4] = struct.pack("<I", item["category"])

    # buyable flag
    block[BUYABLE_OFFSET] = item["buyable"] & 0xFF

    # id
    block[ID_OFFSET:ID_OFFSET + 4] = struct.pack("<I", item["id"])

    return block


# -------------------------------
# SHOP EDITOR GUI
# -------------------------------
class ShopEditor:

    def __init__(self, root):
        self.root = root
        self.root.title("BOTS KR - Shop Editor")
        self.data = None
        self.header = b""
        self.items = []

        self.left = tk.Frame(root)
        self.left.pack(side="left", fill="y", padx=10, pady=10)

        self.right = tk.Frame(root)
        self.right.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        tk.Button(self.left, text="Carregar shop_decoded.bin",
                  command=self.load_file).pack()

        self.listbox = tk.Listbox(self.left, width=40, height=30)
        self.listbox.pack()
        self.listbox.bind("<<ListboxSelect>>", self.load_item)

        # Campos de edição
        self.fields = {}

        row = 0
        for label, key in [
            ("ID", "id"),
            ("Nome", "name"),
            ("Categoria", "category"),
            ("Buyable (0/1)", "buyable"),
        ]:
            tk.Label(self.right, text=label).grid(row=row, column=0, sticky="w")
            entry = tk.Entry(self.right)
            entry.grid(row=row, column=1)
            self.fields[key] = entry
            row += 1

        tk.Button(self.right, text="Salvar alterações", command=self.save_changes).grid(row=row, column=0)
        tk.Button(self.right, text="Adicionar novo item", command=self.add_item).grid(row=row, column=1)
        row += 1

        tk.Button(self.right, text="Remover item", command=self.remove_item).grid(row=row, column=0)
        tk.Button(self.right, text="Salvar shop_new.bin", command=self.export).grid(row=row, column=1)

    # ------------------------------------
    def load_file(self):
        path = filedialog.askopenfilename(title="Selecione shop_decoded.bin")

        if not path:
            return

        try:
            with open(path, "rb") as f:
                self.data = f.read()

            if len(self.data) < HEADER_SIZE:
                raise ValueError("Arquivo muito pequeno para conter cabeçalho e itens")

            self.header = self.data[:HEADER_SIZE]

            self.items = []
            self.listbox.delete(0, tk.END)

            for offset in range(HEADER_SIZE, len(self.data), ITEM_SIZE):
                block = self.data[offset:offset + ITEM_SIZE]
                if len(block) < ITEM_SIZE:
                    break

                item = parse_item(self.data, offset)
                self.items.append(item)
                self.listbox.insert(tk.END, f"{item['id']} - {item['name']}")

            messagebox.showinfo("OK", f"{len(self.items)} itens carregados.")

        except Exception as e:
            messagebox.showerror("Erro", str(e))

    # ------------------------------------
    def load_item(self, event=None):
        if not self.listbox.curselection():
            return

        idx = self.listbox.curselection()[0]
        item = self.items[idx]

        for key, entry in self.fields.items():
            entry.delete(0, tk.END)
            entry.insert(0, str(item[key]))

        self.current_index = idx

    # ------------------------------------
    def save_changes(self):
        idx = self.current_index
        item = self.items[idx]

        item["name"] = self.fields["name"].get()
        item["category"] = int(self.fields["category"].get())
        item["buyable"] = int(self.fields["buyable"].get())

        # atualizar listbox
        self.listbox.delete(idx)
        self.listbox.insert(idx, f"{item['id']} - {item['name']}")

        messagebox.showinfo("OK", "Item atualizado.")

    # ------------------------------------
    def add_item(self):
        # Clona o último item como template
        new = self.items[-1].copy()
        new["id"] += 1
        new["name"] = "NewItem"
        new["category"] = 0
        new["buyable"] = 1
        new["block"] = bytearray(new["block"])

        self.items.append(new)
        self.listbox.insert(tk.END, f"{new['id']} - {new['name']}")

        messagebox.showinfo("OK", "Novo item criado.")

    # ------------------------------------
    def remove_item(self):
        idx = self.current_index
        del self.items[idx]
        self.listbox.delete(idx)
        messagebox.showinfo("OK", "Item removido.")

    # ------------------------------------
    def export(self):
        output = bytearray()
        output += self.header

        for item in self.items:
            output += rebuild_item(item)

        with open("shop_new.bin", "wb") as f:
            f.write(output)

        messagebox.showinfo("OK", "Arquivo salvo como shop_new.bin")


# ------------------------------------
# MAIN
# ------------------------------------
root = tk.Tk()
app = ShopEditor(root)
root.mainloop()
