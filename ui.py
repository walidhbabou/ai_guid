from __future__ import annotations

import json
import threading
import tkinter as tk
from tkinter import scrolledtext
import webbrowser
from PIL import Image, ImageTk
from io import BytesIO
from urllib import request as urllib_request

from main import ask_gemini


class PlacesApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("🌍 Explorateur de Lieux Touristiques")
        self.root.geometry("1300x900")
        self.root.minsize(1000, 700)

        self.places_data = []
        self.photo_refs = []

        self._build_ui()

    def _build_ui(self) -> None:
        # Configure style
        self.root.configure(bg="#f0f0f0")

        # ===== TOP SEARCH SECTION =====
        top_section = tk.Frame(self.root, bg="white", height=160)
        top_section.pack(fill=tk.X, padx=0, pady=0)
        top_section.pack_propagate(False)

        # Header
        header = tk.Frame(top_section, bg="#1a5490", height=80)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        title = tk.Label(
            header,
            text="🌍 Explorateur de Lieux Touristiques",
            font=("Segoe UI", 18, "bold"),
            bg="#1a5490",
            fg="white",
        )
        title.pack(side=tk.LEFT, padx=20, pady=20)

        # Search section
        search_box = tk.Frame(top_section, bg="white", padx=20, pady=16)
        search_box.pack(fill=tk.BOTH, expand=True)

        search_label = tk.Label(
            search_box,
            text="Cherche des lieux ou des villes:",
            font=("Segoe UI", 11, "bold"),
            bg="white",
            fg="#333",
        )
        search_label.pack(anchor="w", pady=(0, 8))

        # Input frame
        input_frame = tk.Frame(search_box, bg="white")
        input_frame.pack(fill=tk.X, pady=(0, 12))

        self.query_input = tk.Entry(
            input_frame,
            font=("Segoe UI", 11),
            width=60,
            relief=tk.FLAT,
            bd=1,
        )
        self.query_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))
        self.query_input.insert(0, "Meilleurs endroits à visiter à Rabat")

        # Buttons
        self.search_btn = tk.Button(
            input_frame,
            text="🔍 Chercher",
            font=("Segoe UI", 11, "bold"),
            bg="#1a5490",
            fg="white",
            padx=24,
            pady=8,
            relief=tk.FLAT,
            command=self._on_search,
        )
        self.search_btn.pack(side=tk.LEFT, padx=(0, 8))

        clear_btn = tk.Button(
            input_frame,
            text="✕ Effacer",
            font=("Segoe UI", 10),
            bg="#e0e0e0",
            fg="#333",
            padx=16,
            pady=8,
            relief=tk.FLAT,
            command=self._on_clear,
        )
        clear_btn.pack(side=tk.LEFT)

        # Status
        self.status_var = tk.StringVar(value="Prêt à chercher des lieux")
        status_label = tk.Label(
            search_box,
            textvariable=self.status_var,
            font=("Segoe UI", 9),
            bg="white",
            fg="#666",
        )
        status_label.pack(anchor="w")

        # ===== MAIN CONTENT AREA =====
        main_area = tk.Frame(self.root, bg="#f0f0f0")
        main_area.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        # Canvas with scrollbar
        canvas_frame = tk.Frame(main_area, bg="white")
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(canvas_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas = tk.Canvas(
            canvas_frame,
            bg="white",
            yscrollcommand=scrollbar.set,
            highlightthickness=0,
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.canvas.yview)

        # Scrollable container
        self.container = tk.Frame(self.canvas, bg="white")
        self.canvas_window = self.canvas.create_window(0, 0, window=self.container, anchor="nw")

        def on_frame_configure(event: tk.Event) -> None:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        self.container.bind("<Configure>", on_frame_configure)
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))

    def _on_search(self) -> None:
        query = self.query_input.get().strip()
        if not query:
            self.status_var.set("⚠️ Saisis une recherche")
            return

        self.search_btn.config(state=tk.DISABLED)
        self.status_var.set("🔄 Recherche en cours...")
        self._clear_results()

        thread = threading.Thread(target=self._fetch_places, args=(query,), daemon=True)
        thread.start()

    def _fetch_places(self, query: str) -> None:
        try:
            places = ask_gemini(query)
            self.root.after(0, self._display_places, places)
        except Exception as e:
            self.root.after(0, lambda: self.status_var.set(f"❌ Erreur: {str(e)[:50]}"))
            self.root.after(0, lambda: self.search_btn.config(state=tk.NORMAL))

    def _clear_results(self) -> None:
        for widget in self.container.winfo_children():
            widget.destroy()
        self.places_data = []
        self.photo_refs = []

    def _display_places(self, places: list[dict]) -> None:
        self._clear_results()
        self.places_data = places

        if not places:
            empty = tk.Label(
                self.container,
                text="❌ Aucun résultat trouvé\n\nEssaie une autre recherche.",
                font=("Segoe UI", 12),
                bg="white",
                fg="#999",
                pady=40,
            )
            empty.pack()
            self.status_var.set("Aucun résultat")
            self.search_btn.config(state=tk.NORMAL)
            return

        for place in places:
            self._create_place_card(place)

        self.status_var.set(f"✓ {len(places)} lieu(x) trouvé(s)")
        self.search_btn.config(state=tk.NORMAL)

    def _create_place_card(self, place: dict) -> None:
        """Crée une carte lieu avec image, détails et boutons."""
        card = tk.Frame(self.container, bg="white", relief=tk.FLAT, bd=0)
        card.pack(fill=tk.X, pady=(0, 12), padx=4)

        # Border bottom
        border = tk.Frame(card, bg="#e0e0e0", height=1)
        border.pack(fill=tk.X, side=tk.BOTTOM)

        # Main content
        content = tk.Frame(card, bg="white")
        content.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        # LEFT: Image
        image_container = tk.Frame(content, bg="#f5f5f5", width=220, height=160)
        image_container.pack(side=tk.LEFT, padx=(0, 20))
        image_container.pack_propagate(False)

        self._load_image(place.get("image_url"), image_container)

        # RIGHT: Details
        details = tk.Frame(content, bg="white")
        details.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ---- Title + Rating Row ----
        title_row = tk.Frame(details, bg="white")
        title_row.pack(fill=tk.X, pady=(0, 8))

        title = tk.Label(
            title_row,
            text=place.get("name", "Lieu"),
            font=("Segoe UI", 13, "bold"),
            bg="white",
            fg="#1a5490",
            anchor="w",
        )
        title.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Rating
        if place.get("rating"):
            rating_text = f"⭐ {place['rating']}/5"
            if place.get("reviews_count"):
                rating_text += f" ({place['reviews_count']} avis)"
            rating_label = tk.Label(
                title_row,
                text=rating_text,
                font=("Segoe UI", 9),
                bg="white",
                fg="#f39c12",
            )
            rating_label.pack(side=tk.RIGHT, padx=(12, 0))

        # ---- Category + Location ----
        if place.get("category"):
            cat = tk.Label(
                details,
                text=f"📂 {place['category']}",
                font=("Segoe UI", 9),
                bg="white",
                fg="#3498db",
                anchor="w",
            )
            cat.pack(fill=tk.X, pady=(0, 4))

        location_parts = []
        if place.get("address"):
            location_parts.append(place["address"])
        if place.get("city"):
            location_parts.append(place["city"])
        if place.get("country"):
            location_parts.append(place["country"])

        if location_parts:
            loc = tk.Label(
                details,
                text="📍 " + ", ".join(location_parts),
                font=("Segoe UI", 9),
                bg="white",
                fg="#666",
                anchor="w",
                wraplength=700,
                justify=tk.LEFT,
            )
            loc.pack(fill=tk.X, pady=(0, 8))

        # ---- Description ----
        if place.get("description"):
            desc = tk.Label(
                details,
                text=place["description"],
                font=("Segoe UI", 9),
                bg="white",
                fg="#555",
                anchor="nw",
                wraplength=700,
                justify=tk.LEFT,
            )
            desc.pack(fill=tk.X, pady=(0, 10))

        # ---- Tags + Price Row ----
        tags_price = tk.Frame(details, bg="white")
        tags_price.pack(fill=tk.X, pady=(0, 12))

        if place.get("price_level"):
            price = tk.Label(
                tags_price,
                text=f"💰 {place['price_level']}",
                font=("Segoe UI", 9, "bold"),
                bg="white",
                fg="#e74c3c",
            )
            price.pack(side=tk.LEFT, padx=(0, 12))

        if place.get("tags"):
            tags_text = " • ".join(place["tags"][:3])
            tags = tk.Label(
                tags_price,
                text=f"🏷️ {tags_text}",
                font=("Segoe UI", 8),
                bg="white",
                fg="#999",
            )
            tags.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # ---- Action Buttons ----
        buttons = tk.Frame(details, bg="white")
        buttons.pack(fill=tk.X)

        if place.get("map_url"):
            map_btn = tk.Button(
                buttons,
                text="🗺️ Voir sur Google Maps",
                font=("Segoe UI", 9, "bold"),
                bg="#e74c3c",
                fg="white",
                padx=16,
                pady=8,
                relief=tk.FLAT,
                command=lambda url=place["map_url"]: webbrowser.open(url),
            )
            map_btn.pack(side=tk.LEFT, padx=(0, 8))

        if place.get("image_url"):
            img_btn = tk.Button(
                buttons,
                text="🖼️ Voir image en HD",
                font=("Segoe UI", 9),
                bg="#3498db",
                fg="white",
                padx=16,
                pady=8,
                relief=tk.FLAT,
                command=lambda url=place["image_url"]: webbrowser.open(url),
            )
            img_btn.pack(side=tk.LEFT)

    def _load_image(self, image_url: str | None, container: tk.Frame) -> None:
        """Charge une image depuis l'URL."""
        if not image_url:
            placeholder = tk.Label(
                container,
                text="📷\nPas d'image",
                font=("Segoe UI", 11),
                bg="#f5f5f5",
                fg="#ccc",
            )
            placeholder.pack(fill=tk.BOTH, expand=True)
            return

        try:
            req = urllib_request.Request(
                image_url,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib_request.urlopen(req, timeout=5) as resp:
                img_data = resp.read()

            img = Image.open(BytesIO(img_data))
            img.thumbnail((220, 160), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)

            self.photo_refs.append(photo)

            label = tk.Label(container, image=photo, bg="white")
            label.image = photo
            label.pack(fill=tk.BOTH, expand=True)
        except Exception as e:
            error = tk.Label(
                container,
                text="❌\nImage\nindisponible",
                font=("Segoe UI", 9),
                bg="#f5f5f5",
                fg="#999",
            )
            error.pack(fill=tk.BOTH, expand=True)

    def _on_clear(self) -> None:
        self._clear_results()
        self.status_var.set("Prêt à chercher des lieux")


def main() -> None:
    root = tk.Tk()
    app = PlacesApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
