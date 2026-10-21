"use client";

import { useState } from "react";

import AdminAddCatalogForm, { type AdminAddCatalogFormConfig } from "@/components/admin/admin_add_catalog_form";
import AdminAnimeTable from "@/components/admin/admin_anime_table";
import { ANIME_ADMIN_ROUTES } from "@/components/admin/admin_routes";
import { addAdminAnime } from "@/lib/api/admin";

const addAnimeFormConfig: AdminAddCatalogFormConfig = {
  addItem: addAdminAnime,
  description:
    "Paste a MyAnimeList anime URL. Its metadata and available episodes will be synchronized automatically.",
  errorMessage: "Unable to add anime",
  headingId: "add-anime-title",
  inputId: "mal-url",
  inputLabel: "MyAnimeList URL",
  placeholder: "https://myanimelist.net/anime/52991",
  routes: ANIME_ADMIN_ROUTES,
  submitLabel: "Add Anime",
  submittingLabel: "Adding anime...",
  title: "Add Anime",
};

export default function AdminAnimeManagement() {
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <>
      <AdminAddCatalogForm
        config={addAnimeFormConfig}
        onAdded={() => setRefreshKey((current) => current + 1)}
      />
      <AdminAnimeTable refreshKey={refreshKey} />
    </>
  );
}
