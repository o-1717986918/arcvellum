import { readFile } from "node:fs/promises";
import type { AuthOperationOptions, Credential, CredentialInfo, CredentialStore } from "@earendil-works/pi-ai";

export class ReadOnlyJsonCredentialStore implements CredentialStore {
	private loaded?: Record<string, Credential>;
	private readonly authPath: string;

	constructor(authPath: string) {
		this.authPath = authPath;
	}

	async read(providerId: string, _options?: AuthOperationOptions): Promise<Credential | undefined> {
		return (await this.load())[providerId];
	}

	async list(_options?: AuthOperationOptions): Promise<readonly CredentialInfo[]> {
		return Object.entries(await this.load()).map(([providerId, credential]) => ({
			providerId,
			type: credential.type,
		}));
	}

	async modify(
		_providerId: string,
		_fn: (current: Credential | undefined) => Promise<Credential | undefined>,
		_options?: AuthOperationOptions,
	): Promise<Credential | undefined> {
		throw new Error("ArcVellum Pi Worker credential storage is read-only");
	}

	async delete(_providerId: string, _options?: AuthOperationOptions): Promise<void> {
		throw new Error("ArcVellum Pi Worker credential storage is read-only");
	}

	private async load(): Promise<Record<string, Credential>> {
		if (this.loaded) return this.loaded;
		let text: string;
		try {
			text = await readFile(this.authPath, "utf8");
		} catch (error) {
			if ((error as NodeJS.ErrnoException).code === "ENOENT") return (this.loaded = {});
			throw error;
		}
		const parsed: unknown = JSON.parse(text);
		if (!isRecord(parsed)) throw new Error("Pi auth.json must contain an object");
		const credentials: Record<string, Credential> = {};
		for (const [provider, value] of Object.entries(parsed)) {
			if (!isRecord(value) || (value.type !== "api_key" && value.type !== "oauth")) {
				throw new Error(`Pi auth.json contains an invalid credential for ${provider}`);
			}
			credentials[provider] = value as unknown as Credential;
		}
		this.loaded = credentials;
		return credentials;
	}
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}
