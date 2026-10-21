"use client";

import { useState } from "react";

import AdminAddCatalogForm, { type AdminAddCatalogFormConfig } from "@/components/admin/admin_add_catalog_form";
import AdminMangaTable from "@/components/admin/admin_manga_table";
import { MANGA_ADMIN_ROUTES } from "@/components/admin/admin_routes";
import { addAdminManga } from "@/lib/api/admin";

const addMangaFormConfig: AdminAddCatalogFormConfig = {
  addItem: addAdminManga,
  description:
    "Paste a MyAnimeList manga URL. Metadata and available MangaKatana chapters will be synchronized automatically.",
  errorMessage: "Unable to add manga",
  headingId: "add-manga-title",
  inputId: "manga-mal-url",
  inputLabel: "MyAnimeList manga URL",
  placeholder: "https://myanimelist.net/manga/2",
  routes: MANGA_ADMIN_ROUTES,
  submitLabel: "Add Manga",
  submittingLabel: "Adding manga...",
  title: "Add Manga",
};

export default function AdminMangaManagement() {
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <>
      <AdminAddCatalogForm
        config={addMangaFormConfig}
        onAdded={() => setRefreshKey((current) => current + 1)}
      />
      <AdminMangaTable refreshKey={refreshKey} />
    </>
  );
}
