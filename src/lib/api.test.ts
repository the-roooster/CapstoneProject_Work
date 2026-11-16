import { afterEach, describe, expect, it, vi } from "vitest";
import { get, getToken, login, tokenEmail } from "./api";

function storage(initial: Record<string, string> = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
    removeItem: (key: string) => { values.delete(key); },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("API authentication", () => {
  it("attaches the bearer token", async () => {
    vi.stubEnv("VITE_API_URL", "http://localhost:8000/api/v1");
    vi.stubGlobal("localStorage", storage({ sentinel_token: "abc" }));
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await get("/users");
    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8000/api/v1/users");
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get("Authorization")).toBe("Bearer abc");
  });

  it("clears the token and redirects on 401", async () => {
    const local = storage({ sentinel_token: "abc" });
    const assign = vi.fn();
    vi.stubGlobal("localStorage", local);
    vi.stubGlobal("window", { location: { pathname: "/dashboard", assign } });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "expired" }), { status: 401 })));
    await expect(get("/users")).rejects.toThrow("expired");
    expect(local.getItem("sentinel_token")).toBeNull();
    expect(assign).toHaveBeenCalledWith("/auth");
  });

  it("posts form credentials and stores the access token", async () => {
    const local = storage();
    vi.stubGlobal("localStorage", local);
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ access_token: "fresh", token_type: "bearer" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await login("alice@example.com", "secret");
    expect(fetchMock.mock.calls[0][1].body.toString()).toBe("username=alice%40example.com&password=secret");
    expect(getToken()).toBe("fresh");
  });

  it("handles unavailable storage and decodes a JWT subject", () => {
    vi.stubGlobal("localStorage", { getItem() { throw new Error("blocked"); } });
    expect(getToken()).toBeNull();
    const payload = btoa(JSON.stringify({ sub: "alice@example.com" })).replace(/=/g, "");
    expect(tokenEmail(`x.${payload}.x`)).toBe("alice@example.com");
    expect(tokenEmail("invalid")).toBe("");
  });
});
