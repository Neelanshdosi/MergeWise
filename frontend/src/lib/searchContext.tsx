"use client";

import React, { createContext, useContext, useState } from "react";

export type SortOption = "match" | "newest" | "stars";

interface SearchContextType {
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  sortBy: SortOption;
  setSortBy: (sort: SortOption) => void;
  languageFilter: string;
  setLanguageFilter: (lang: string) => void;
  isPipelineDetailsOpen: boolean;
  setIsPipelineDetailsOpen: (open: boolean | ((prev: boolean) => boolean)) => void;
}

const SearchContext = createContext<SearchContextType>({
  searchQuery: "",
  setSearchQuery: () => {},
  sortBy: "match",
  setSortBy: () => {},
  languageFilter: "all",
  setLanguageFilter: () => {},
  isPipelineDetailsOpen: false,
  setIsPipelineDetailsOpen: () => {},
});

export function SearchProvider({ children }: { children: React.ReactNode }) {
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState<SortOption>("match");
  const [languageFilter, setLanguageFilter] = useState("all");
  const [isPipelineDetailsOpen, setIsPipelineDetailsOpen] = useState(false);

  return (
    <SearchContext.Provider
      value={{
        searchQuery,
        setSearchQuery,
        sortBy,
        setSortBy,
        languageFilter,
        setLanguageFilter,
        isPipelineDetailsOpen,
        setIsPipelineDetailsOpen,
      }}
    >
      {children}
    </SearchContext.Provider>
  );
}

export function useSearch() {
  return useContext(SearchContext);
}

