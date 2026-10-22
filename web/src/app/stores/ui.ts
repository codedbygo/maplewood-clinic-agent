import { create } from "zustand";
import { persist } from "zustand/middleware";

// Client-only UI preferences. Nothing the server owns lives here.
interface UiState {
  theme: "light" | "dark";
  toggleTheme: () => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      theme: "light",
      toggleTheme: () => set((s) => ({ theme: s.theme === "light" ? "dark" : "light" })),
    }),
    { name: "maplewood-console-ui" },
  ),
);
