from __future__ import annotations

import json
import os
import sys
import threading
import tkinter as tk
from tkinter import scrolledtext
import webbrowser
import traceback
from PIL import Image, ImageTk
from io import BytesIO
from urllib import request as urllib_request

from main import ask_gemini


class PlacesApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("🌍 Explorateur de Lieux Touristiques")
        self.root.geometry("1400x950")
        self.root.minsize(1000, 700)

        self.places_data = []
        self.photo_refs = []

        self._build_ui()

    def _build_ui(self) -> None:
        # Configure style
        self.root.configure(bg="#f5f5f5")

        # ===== TOP SEARCH SECTION =====
        top_section = tk.Frame(self.root, bg="white", height=180)
        top_section.pack(fill=tk.X, padx=0, pady=0)
        top_section.pack_propagate(False)

        # Header
        header = tk.Frame(top_section, bg="#0d47a1", height=90)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        title = tk.Label(
            header,
            text="🌍 Explorateur de Lieux Touristiques",
            font=("Segoe UI", 20, "bold"),
            bg="#0d47a1",
            fg="white",
        )
        title.pack(side=tk.LEFT, padx=25, pady=25)

        # Search section
        search_box = tk.Frame(top_section, bg="white", padx=25, pady=18)
        search_box.pack(fill=tk.BOTH, expand=True)

        search_label = tk.Label(
            search_box,
          
        )
        search_label.pack(anchor="w", pady=(0, 10))

        # Input frame
        input_frame = tk.Frame(search_box, bg="white")
        input_frame.pack(fill=tk.X, pady=(0, 14))

        self.query_input = tk.Entry(
            input_frame,
            font=("Segoe UI", 12),
            width=70,
            relief=tk.FLAT,
            bd=2,
            bg="#f9f9f9",
            fg="#333",
        )
        self.query_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12), ipady=6)
        self.query_input.insert(0, "Meilleurs endroits à visiter à Rabat")

        # Buttons
        self.search_btn = tk.Button(
            input_frame,
            text="🔍 Chercher",
            font=("Segoe UI", 11, "bold"),
            bg="#0d47a1",
            fg="white",
            padx=28,
            pady=8,
            relief=tk.FLAT,
            cursor="hand2",
            command=self._on_search,
        )
        self.search_btn.pack(side=tk.LEFT, padx=(0, 10))

        clear_btn = tk.Button(
            input_frame,
            text="✕ Effacer",
            font=("Segoe UI", 11),
            bg="#eceff1",
            fg="#333",
            padx=18,
            pady=8,
            relief=tk.FLAT,
            cursor="hand2",
            command=self._on_clear,
        )
        clear_btn.pack(side=tk.LEFT)

        # Status
        self.status_var = tk.StringVar(value="✓ Prêt à chercher des lieux")
        status_label = tk.Label(
            search_box,
            textvariable=self.status_var,
            font=("Segoe UI", 10),
            bg="white",
            fg="#666",
        )
        status_label.pack(anchor="w")

        # ===== MAIN CONTENT AREA =====
        main_area = tk.Frame(self.root, bg="#f5f5f5")
        main_area.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Canvas with scrollbar
        canvas_frame = tk.Frame(main_area, bg="#f5f5f5")
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(canvas_frame, bg="#ddd", activebackground="#999")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 8))

        self.canvas = tk.Canvas(
            canvas_frame,
            bg="#f5f5f5",
            yscrollcommand=scrollbar.set,
            highlightthickness=0,
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))
        scrollbar.config(command=self.canvas.yview)

        # Scrollable container
        self.container = tk.Frame(self.canvas, bg="#f5f5f5")
        self.canvas_window = self.canvas.create_window(0, 0, window=self.container, anchor="nw")

        def on_frame_configure(event: tk.Event) -> None:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        def on_canvas_configure(event: tk.Event) -> None:
            self.canvas.itemconfig(self.canvas_window, width=event.width - 16)

        self.container.bind("<Configure>", on_frame_configure)
        self.canvas.bind("<Configure>", on_canvas_configure)

        # Mousewheel binding
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

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
                font=("Segoe UI", 14),
                bg="#f5f5f5",
                fg="#999",
                pady=60,
            )
            empty.pack()
            self.status_var.set("Aucun résultat")
            self.search_btn.config(state=tk.NORMAL)
            return

        for idx, place in enumerate(places):
            self._create_place_card(place, idx + 1)

        self.status_var.set(f"✓ {len(places)} lieu(x) trouvé(s)")
        self.search_btn.config(state=tk.NORMAL)

    def _create_place_card(self, place: dict, index: int) -> None:
        """Crée une carte lieu avec image, détails et boutons."""
        card = tk.Frame(self.container, bg="white", relief=tk.FLAT, bd=0)
        card.pack(fill=tk.X, pady=12, padx=16)

        # Shadow effect with border
        border = tk.Frame(card, bg="#e0e0e0", height=1)
        border.pack(fill=tk.X, side=tk.BOTTOM)

        # Main content
        content = tk.Frame(card, bg="white")
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=18)

        # Index badge
        badge = tk.Label(
            content,
            text=f"#{index}",
            font=("Segoe UI", 10, "bold"),
            bg="#0d47a1",
            fg="white",
            padx=10,
            pady=4,
            relief=tk.FLAT,
        )
        badge.pack(anchor="w", pady=(0, 12))

        # Row: Image + Details
        row = tk.Frame(content, bg="white")
        row.pack(fill=tk.BOTH, expand=True)

        # LEFT: Image
        image_container = tk.Frame(row, bg="#f5f5f5", width=240, height=180)
        image_container.pack(side=tk.LEFT, padx=(0, 24), fill=tk.BOTH)
        image_container.pack_propagate(False)

        self._load_image(place.get("image_url"), image_container)

        # RIGHT: Details
        details = tk.Frame(row, bg="white")
        details.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ---- Title + Rating Row ----
        title_row = tk.Frame(details, bg="white")
        title_row.pack(fill=tk.X, pady=(0, 10))

        title = tk.Label(
            title_row,
            text=place.get("name", "Lieu"),
            font=("Segoe UI", 14, "bold"),
            bg="white",
            fg="#0d47a1",
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
                font=("Segoe UI", 10, "bold"),
                bg="white",
                fg="#f39c12",
            )
            rating_label.pack(side=tk.RIGHT, padx=(12, 0))

        # ---- Category + Location ----
        info_frame = tk.Frame(details, bg="white")
        info_frame.pack(fill=tk.X, pady=(0, 8))

        if place.get("category"):
            cat = tk.Label(
                info_frame,
                text=f"📂 {place['category'].upper()}",
                font=("Segoe UI", 10, "bold"),
                bg="white",
                fg="#3498db",
                anchor="w",
            )
            cat.pack(side=tk.LEFT, padx=(0, 16))

        if place.get("price_level"):
            price = tk.Label(
                info_frame,
                text=f"💰 {place['price_level']}",
                font=("Segoe UI", 10, "bold"),
                bg="white",
                fg="#e74c3c",
            )
            price.pack(side=tk.LEFT)

        # ---- Location ----
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
                font=("Segoe UI", 10),
                bg="white",
                fg="#555",
                anchor="w",
                wraplength=800,
                justify=tk.LEFT,
            )
            loc.pack(fill=tk.X, pady=(0, 10))

        # ---- Description ----
        if place.get("description"):
            desc = tk.Label(
                details,
                text=place["description"],
                font=("Segoe UI", 10),
                bg="white",
                fg="#666",
                anchor="nw",
                wraplength=800,
                justify=tk.LEFT,
            )
            desc.pack(fill=tk.X, pady=(0, 12))

        # ---- Tags ----
        if place.get("tags"):
            tags_text = " • ".join(place["tags"][:4])
            tags = tk.Label(
                details,
                text=f"🏷️ {tags_text}",
                font=("Segoe UI", 9),
                bg="white",
                fg="#999",
                anchor="w",
            )
            tags.pack(fill=tk.X, pady=(0, 14))

        # ---- Action Buttons ----
        buttons = tk.Frame(details, bg="white")
        buttons.pack(fill=tk.X)

        if place.get("map_url"):
            map_btn = tk.Button(
                buttons,
                text="🗺️ Google Maps",
                font=("Segoe UI", 10, "bold"),
                bg="#e74c3c",
                fg="white",
                padx=18,
                pady=10,
                relief=tk.FLAT,
                cursor="hand2",
                command=lambda url=place["map_url"]: webbrowser.open(url),
            )
            map_btn.pack(side=tk.LEFT, padx=(0, 10))

        if place.get("image_url"):
            img_btn = tk.Button(
                buttons,
                text="🖼️ Voir image",
                font=("Segoe UI", 10),
                bg="#3498db",
                fg="white",
                padx=18,
                pady=10,
                relief=tk.FLAT,
                cursor="hand2",
                command=lambda url=place["image_url"]: webbrowser.open(url),
            )
            img_btn.pack(side=tk.LEFT)

    def _load_image(self, image_url: str | None, container: tk.Frame) -> None:
        """Charge une image depuis l'URL."""
        if not image_url:
            placeholder = tk.Label(
                container,
                text="📷\nPas d'image",
                font=("Segoe UI", 13, "bold"),
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
            img.thumbnail((240, 180), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)

            self.photo_refs.append(photo)

            label = tk.Label(container, image=photo, bg="white")
            label.image = photo
            label.pack(fill=tk.BOTH, expand=True)
        except Exception as e:
            error = tk.Label(
                container,
                text="❌\nImage\nindisponible",
                font=("Segoe UI", 10, "bold"),
                bg="#f5f5f5",
                fg="#999",
            )
            error.pack(fill=tk.BOTH, expand=True)

    def _on_clear(self) -> None:
        self._clear_results()
        self.status_var.set("✓ Prêt à chercher des lieux")


def main() -> None:
    root = tk.Tk()
    app = PlacesApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
