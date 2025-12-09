import tkinter as tk
from tkinter import filedialog, messagebox
import struct

BLOCK_SIZE = 128  # blocos detectados (2 por item)
ITEM_SIZE = BLOCK_SIZE * 2  # 256 bytes por item


# -------------------------------
# Função para ler um item
# -------------------------------
def parse_item(data, offset):
    block1 = data[offset:offset + BLOCK_SIZE]
    block2 = data[offset + BLOCK_SIZE:offset + ITEM_SIZE]

    # Nome sempre no final do bloco
    name_raw = block1[0x38:0x38 + 32]
    name = name_raw.split(b"\x00")[0].decode("ascii", errors="ignore")

    # ID little endian nos bytes 0x30–0x34
    item_id = struct.unpack("<I", block1[0x30:0x34])[0]

    # categoria = primeiros 2 bytes
    category = struct.unpack("<H", block1[0:2])[0]

    # flag buyable = bytes 0x2C–0x2E
    buy_flag = block1[0x2C]

    return {
        "offset": offset,
        "id": item_id,
        "name": name,
        "category": category,
        "buyable": buy_flag,
        "block1": bytearray(block1),
        "block2": bytearray(block2)
    }


# -------------------------------
# Função para reconstruir itens
# -------------------------------
def rebuild_item(item):
    b1 = item["block1"]
    b2 = item["block2"]

    # nome
    name_bytes = item["name"].encode("ascii", errors="ignore")
    name_bytes = name_bytes[:31] + b"\x00"
    b1[0x38:0x38 + len(name_bytes)] = name_bytes

    # categoria
    b1[0:2] = struct.pack("<H", item["category"])

    # buyable flag
    b1[0x2C] = item["buyable"]

    return b1 + b2


# -------------------------------
# SHOP EDITOR GUI
# -------------------------------
class ShopEditor:

    def __init__(self, root):
        self.root = root
        self.root.title("BOTS KR - Shop Editor")
        self.data = None
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

            self.items = []
            self.listbox.delete(0, tk.END)

            for offset in range(0, len(self.data), ITEM_SIZE):
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
        new["block1"] = bytearray(new["block1"])
        new["block2"] = bytearray(new["block2"])

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
