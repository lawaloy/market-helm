import { afterEach, describe, expect, it, vi } from 'vitest';
import api, { alertsApi } from './api';

describe('alertsApi.initConfig force query', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('omits force on the default Start watching call', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: { message: 'ok' } } as never);

    await alertsApi.initConfig();

    expect(post).toHaveBeenCalledTimes(1);
    expect(post).toHaveBeenCalledWith('/api/alerts/init', null, { params: undefined });
    const params = post.mock.calls[0][2]?.params as { force?: boolean } | undefined;
    expect(params?.force).toBeUndefined();
  });

  it('sends force=true only when recovery explicitly requests overwrite', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: { message: 'ok' } } as never);

    await alertsApi.initConfig(true);

    expect(post).toHaveBeenCalledWith('/api/alerts/init', null, {
      params: { force: true },
    });
  });
});
