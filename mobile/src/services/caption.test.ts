import { buildMockCaption } from './caption';

describe('buildMockCaption', () => {
  it('creates an editable caption from information without network access', () => {
    const result = buildMockCaption({ information: 'Calm Content Workflow. Plan once and reuse ideas.', goal: 'Educate' });
    expect(result.caption).toContain('Calm Content Workflow');
    expect(result.caption).toContain('Plan once and reuse ideas.');
    expect(result.hashtags).toContain('#calm');
    expect(result.hashtags).toContain('#creatormind');
  });
});
