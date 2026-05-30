"use client";

import { useEffect } from "react";
import { getExpiresAt } from "@/lib/auth";
import { refreshToken } from "@/lib/api";

const REFRESH_BEFORE_MS = 10 * 60 * 1000; // 10 minutes before expiry

export function useTokenRefresh() {
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;

    function scheduleRefresh() {
      const expiry = getExpiresAt();
      if (!expiry) return;
      const msUntilRefresh = new Date(expiry).getTime() - Date.now() - REFRESH_BEFORE_MS;
      if (msUntilRefresh <= 0) {
        // Already within the refresh window — refresh immediately.
        refreshToken().then(scheduleRefresh);
        return;
      }
      timer = setTimeout(() => {
        refreshToken().then(scheduleRefresh);
      }, msUntilRefresh);
    }

    scheduleRefresh();
    return () => clearTimeout(timer);
  }, []);
}
