import {
  api,
  authorizedFetch,
  connectEventStream,
  query,
  streamApi,
  type ApiTransport,
} from "./api";

// Keep transport access lazy so feature clients remain easy to mock with the
// existing low-level API seam while components migrate to semantic clients.
export const featureTransport: ApiTransport = {
  request: (...args) => api(...args),
  authorizedFetch: (...args) => authorizedFetch(...args),
  stream: (...args) => streamApi(...args),
  connect: (...args) => connectEventStream(...args),
  query: (...args) => query(...args),
};
