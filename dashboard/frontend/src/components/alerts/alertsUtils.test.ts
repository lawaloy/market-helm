import { describe, expect, it } from 'vitest';
import { buildNotifications, canPersistConfig, emptyConfig } from './alertsUtils';
import type { AlertsConfig, ChannelStatus } from '../../types';

describe('buildNotifications', () => {
  it('always includes log and appends enabled channels', () => {
    expect(buildNotifications(false, false)).toEqual(['log']);
    expect(buildNotifications(true, false)).toEqual(['log', 'email']);
    expect(buildNotifications(false, true)).toEqual(['log', 'webhook']);
    expect(buildNotifications(true, true)).toEqual(['log', 'email', 'webhook']);
  });
});

describe('canPersistConfig', () => {
  const channelsOff: ChannelStatus = {
    email_smtp: false,
    email_recipients: false,
    webhook_url: false,
  };
  const channelsWebhookSaved: ChannelStatus = {
    email_smtp: false,
    email_recipients: false,
    webhook_url: true,
  };

  function config(partial: Partial<AlertsConfig['defaults']>): AlertsConfig {
    const base = emptyConfig();
    return {
      ...base,
      defaults: { ...base.defaults, ...partial },
    };
  }

  it('rejects when both delivery channels are off', () => {
    expect(canPersistConfig(config({ notify_email: false, notify_webhook: false }), null, '')).toBe(
      'Turn on email or Discord/Slack.',
    );
  });

  it('rejects email-on without an address', () => {
    expect(
      canPersistConfig(config({ notify_email: true, notify_webhook: false, email_to: '  ' }), null, ''),
    ).toBe('Enter your email address, or turn off email notifications.');
  });

  it('rejects webhook-on without a saved URL or draft', () => {
    expect(
      canPersistConfig(
        config({ notify_email: false, notify_webhook: true }),
        channelsOff,
        '   ',
      ),
    ).toBe('Paste a webhook URL, or turn off Discord/Slack notifications.');
  });

  it('allows webhook-on when a secret is already saved and draft is blank', () => {
    expect(
      canPersistConfig(
        config({ notify_email: false, notify_webhook: true }),
        channelsWebhookSaved,
        '',
      ),
    ).toBeNull();
  });

  it('allows email-on with a trimmed address', () => {
    expect(
      canPersistConfig(
        config({ notify_email: true, notify_webhook: false, email_to: 'user@example.com' }),
        null,
        '',
      ),
    ).toBeNull();
  });
});
