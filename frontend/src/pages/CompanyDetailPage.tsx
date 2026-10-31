import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api, ApiError } from '../lib/api';
import type { CompanyDetail, SourceRecord } from '../lib/types';
import { formatDate, getQualificationLabel, getStatusColor } from '../lib/format';
import {
  Card, CardHeader, CardContent,
  Badge, Button, Table, TableHeader, TableBody, TableRow, TableCell, TableHead,
  Flex, Heading, Text, Stack
} from '../components/ui';

export function CompanyDetailPage() {
  const { campaignId, companyId } = useParams<{ campaignId?: string; companyId: string }>();
  const navigate = useNavigate();
  const [company, setCompany] = useState<CompanyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [qualifying, setQualifying] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [statusNotice, setStatusNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    if (!companyId) return;
    try {
      setLoading(true);
      const data = await api.getCompany(Number(companyId));
      setCompany(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load company');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [companyId]);

  const handleRunQualification = async () => {
    if (!company) return;
    setQualifying(true);
    setStatusNotice(null);
    try {
      const run = await api.createRun({
        campaign_id: company.campaign_id,
        company_id: company.id,
      });
      setStatusNotice(`Qualification workflow #${run.id} started. Evaluating sources and generating briefing...`);
      // Reload company state to get updated scores and brief
      const updated = await api.getCompany(company.id);
      setCompany(updated);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Failed to run qualification');
    } finally {
      setQualifying(false);
    }
  };

  const handleApprove = async () => {
    if (!company) return;
    setActionLoading(true);
    try {
      const updated = await api.approveCompany(company.id);
      setCompany(updated);
      setStatusNotice('Company approved for outreach (held by Dry-Run safety guard).');
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Failed to approve company');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!company) return;
    setActionLoading(true);
    try {
      const updated = await api.rejectCompany(company.id);
      setCompany(updated);
      setStatusNotice('Company marked as rejected.');
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Failed to reject company');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <Stack gap={4} className="p-4">
        <Text color="muted">Loading company details…</Text>
      </Stack>
    );
  }

  if (error || !company) {
    return (
      <Stack gap={4} className="p-4">
        <Text color="error">{error ?? 'Company not found'}</Text>
        <Button variant="secondary" onClick={() => navigate(-1)}>Back</Button>
      </Stack>
    );
  }

  const scoreColor = getStatusColor(company.qualification_status);
  const approvalColor = getStatusColor(company.approval_status);

  // Group sources by role/provider for the 9-panel briefing
  const sources = company.sources || [];
  const hiringSources = sources.filter(s => s.provider === 'greenhouse' || s.provider === 'remoteok');
  const newsSources = sources.filter(s => s.provider === 'gnews' || s.provider === 'sec');
  const webSources = sources.filter(s => s.provider === 'direct_fetch' || s.source_type === 'company_website');
  const discoverySources = sources.filter(s => s.source_type === 'discovery' || s.provider === 'tavily' || s.provider === 'exa' || s.provider === 'brave');

  return (
    <Stack gap={6} className="p-2 sm:p-4">
      {/* Notifications */}
      {statusNotice && (
        <div className="rounded-lg border border-accent-200 bg-accent-50/70 p-3 text-sm text-accent-800 flex justify-between items-center">
          <span>{statusNotice}</span>
          <button onClick={() => setStatusNotice(null)} className="text-accent-600 hover:text-accent-800 font-bold ml-2">×</button>
        </div>
      )}

      {/* Header */}
      <Flex justify="between" align="center" wrap gap={4} className="bg-surface rounded-xl p-5 border border-line shadow-xs">
        <div>
          <Flex align="center" gap={3} wrap>
            <Heading size="lg" className="text-ink font-bold tracking-tight text-xl sm:text-2xl">{company.canonical_name}</Heading>
            {company.qualification_status ? (
              <Badge color={scoreColor}>{getQualificationLabel(company.qualification_status)}</Badge>
            ) : (
              <Badge color="neutral">Unqualified</Badge>
            )}
            {company.approval_status && (
              <Badge color={approvalColor}>{company.approval_status.replace('_', ' ')}</Badge>
            )}
            {company.is_excluded && (
              <Badge color="danger">Excluded</Badge>
            )}
          </Flex>
          <Text color="muted" size="sm" className="mt-1">
            Campaign #{company.campaign_id} • Origin: <span className="font-medium text-ink">{company.record_kind}</span> • Added: {formatDate(company.created_at)}
          </Text>
        </div>

        <Flex gap={2} wrap align="center">
          <Button variant="secondary" onClick={() => (campaignId ? navigate(`/campaigns/${campaignId}/companies`) : navigate(-1))}>
            ← Back
          </Button>

          <Button 
            variant="primary" 
            loading={qualifying}
            onClick={handleRunQualification}
            title="Runs full LangGraph pipeline: discovery verification, multi-source enrichment, deterministic scoring, and Groq AI research briefing."
          >
            {company.lead_fit_score !== null ? 'Re-run qualification' : 'Run qualification'}
          </Button>
        </Flex>
      </Flex>

      {/* Top 3 Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-xl border border-line bg-surface p-4 shadow-xs">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-subtle">Target Fit Score</p>
          <div className="mt-2 flex items-baseline gap-2">
            <span className={`text-3xl font-extrabold ${scoreColor === 'ok' ? 'text-ok' : scoreColor === 'warn' ? 'text-warn' : 'text-ink'}`}>
              {company.lead_fit_score !== null ? company.lead_fit_score : '—'}
            </span>
            <span className="text-xs text-ink-muted">/ 100</span>
          </div>
          <p className="mt-2 text-xs text-ink-muted">
            {company.qualification_reason || 'Run qualification to calculate fit against campaign rules.'}
          </p>
        </div>

        <div className="rounded-xl border border-line bg-surface p-4 shadow-xs">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-subtle">Evidence Confidence</p>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-ink">
              {company.evidence_confidence !== null ? company.evidence_confidence : '—'}
            </span>
            <span className="text-xs text-ink-muted">/ 100</span>
          </div>
          <p className="mt-2 text-xs text-ink-muted">
            {sources.length > 0 ? `${sources.length} evidence source record(s) logged` : 'No corroborating sources verified yet.'}
          </p>
        </div>

        <div className="rounded-xl border border-line bg-surface p-4 shadow-xs">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-subtle">Approval & Outreach Status</p>
          <div className="mt-2 flex items-center gap-2">
            <span className="text-lg font-bold capitalize text-ink">
              {company.approval_status || 'Pending Review'}
            </span>
            <Badge color="warn">Dry-run only</Badge>
          </div>
          <p className="mt-2 text-xs text-ink-muted">
            All live sends are strictly gated by the backend safety guard.
          </p>
        </div>
      </div>

      {/* Approval Action Card if review required or pending */}
      {company.approval_status !== 'approved' && (
        <Card className="border-accent-200 bg-accent-50/30">
          <CardHeader>
            <Flex justify="between" align="center">
              <div>
                <Heading size="md">Human Approval Gate</Heading>
                <Text color="muted" size="sm">Inspect research and verify confidence before approving for outreach sequence.</Text>
              </div>
              <Flex gap={2}>
                <Button variant="primary" loading={actionLoading} onClick={handleApprove}>
                  Approve Lead
                </Button>
                <Button variant="secondary" loading={actionLoading} onClick={handleReject}>
                  Reject Lead
                </Button>
              </Flex>
            </Flex>
          </CardHeader>
        </Card>
      )}

      {/* 9-Panel Caller Briefing System */}
      <div className="space-y-4">
        <div className="flex items-center justify-between border-b border-line pb-2">
          <div>
            <h2 className="text-lg font-bold text-ink">Caller Briefing Dossier</h2>
            <p className="text-xs text-ink-muted">Everything a sales caller needs to open an informed, high-context conversation.</p>
          </div>
          <span className="text-xs font-mono text-ink-subtle bg-surface-muted px-2 py-1 rounded border border-line">
            9-Panel Specification
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Panel 1: Core Company Profile */}
          <div className="rounded-lg border border-line bg-surface p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-ink-subtle uppercase tracking-wider">1. Company Profile</span>
                <Badge color="neutral">Identity</Badge>
              </div>
              <div className="space-y-2 text-sm mt-3">
                <div>
                  <span className="text-xs text-ink-muted block">Legal / Canonical Name</span>
                  <span className="font-medium text-ink">{company.canonical_name}</span>
                </div>
                <div>
                  <span className="text-xs text-ink-muted block">Website</span>
                  {company.website_domain ? (
                    <a href={company.website_domain.startsWith('http') ? company.website_domain : `https://${company.website_domain}`} target="_blank" rel="noopener noreferrer" className="text-accent-600 hover:underline font-mono text-xs">
                      {company.website_domain}
                    </a>
                  ) : <span className="text-ink-subtle">—</span>}
                </div>
                <div>
                  <span className="text-xs text-ink-muted block">Location</span>
                  <span className="text-ink">{company.country || 'Unknown'}</span>
                </div>
              </div>
            </div>
            <div className="mt-4 pt-2 border-t border-line text-[11px] text-ink-subtle">
              Sector: {company.sector || 'Technology / SaaS'}
            </div>
          </div>

          {/* Panel 2: Verified Size & Structure */}
          <div className="rounded-lg border border-line bg-surface p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-ink-subtle uppercase tracking-wider">2. Size & Structure</span>
                <Badge color="neutral">Scale</Badge>
              </div>
              <div className="space-y-2 text-sm mt-3">
                <div>
                  <span className="text-xs text-ink-muted block">Employee Bracket</span>
                  <span className="font-semibold text-ink">
                    {company.employee_min && company.employee_max ? `${company.employee_min} – ${company.employee_max} employees` : (company.employee_min ? `${company.employee_min}+ employees` : 'Not specified')}
                  </span>
                </div>
                <div>
                  <span className="text-xs text-ink-muted block">Data Source</span>
                  <span className="text-xs text-ink">{company.record_kind === 'test_seed' ? 'Manual campaign seed' : 'Live crawler retrieval'}</span>
                </div>
              </div>
            </div>
            <div className="mt-4 pt-2 border-t border-line text-[11px] text-ink-subtle">
              Confidence: {company.evidence_confidence ? `${company.evidence_confidence}% verified` : 'Awaiting scoring'}
            </div>
          </div>

          {/* Panel 3: Hiring & Growth Signals */}
          <div className="rounded-lg border border-line bg-surface p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-ink-subtle uppercase tracking-wider">3. Hiring & Growth Signals</span>
                <Badge color={hiringSources.length > 0 ? 'ok' : 'neutral'}>
                  {hiringSources.length > 0 ? `${hiringSources.length} signals` : 'No open jobs'}
                </Badge>
              </div>
              <div className="text-xs text-ink-muted mt-3 space-y-1">
                {hiringSources.length > 0 ? (
                  hiringSources.map(s => (
                    <div key={s.id} className="p-2 rounded bg-surface-muted border border-line">
                      <span className="font-medium text-ink block">{s.provider.toUpperCase()}</span>
                      <span className="text-ink-subtle truncate block">{s.source_url}</span>
                    </div>
                  ))
                ) : (
                  <p className="italic text-ink-subtle">Greenhouse & RemoteOK did not return active job vacancies for this domain.</p>
                )}
              </div>
            </div>
            <div className="mt-4 pt-2 border-t border-line text-[11px] text-ink-subtle">
              Provider: Greenhouse / RemoteOK API
            </div>
          </div>

          {/* Panel 4: Press, News & SEC Filings */}
          <div className="rounded-lg border border-line bg-surface p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-ink-subtle uppercase tracking-wider">4. News & Regulatory</span>
                <Badge color={newsSources.length > 0 ? 'ok' : 'neutral'}>
                  {newsSources.length > 0 ? `${newsSources.length} items` : 'None'}
                </Badge>
              </div>
              <div className="text-xs text-ink-muted mt-3 space-y-1.5 max-h-36 overflow-y-auto">
                {newsSources.length > 0 ? (
                  newsSources.map(s => (
                    <div key={s.id} className="p-1.5 rounded bg-surface-muted text-xs">
                      <span className="font-medium text-ink block truncate">{s.provider}</span>
                      {s.source_url && (
                        <a href={s.source_url} target="_blank" rel="noopener noreferrer" className="text-accent-600 hover:underline truncate block">
                          {s.source_url}
                        </a>
                      )}
                    </div>
                  ))
                ) : (
                  <p className="italic text-ink-subtle">No SEC EDGAR or GNews headlines indexed for this specific entity.</p>
                )}
              </div>
            </div>
            <div className="mt-4 pt-2 border-t border-line text-[11px] text-ink-subtle">
              Provider: GNews / SEC EDGAR
            </div>
          </div>

          {/* Panel 5: Web Crawler Signals */}
          <div className="rounded-lg border border-line bg-surface p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-ink-subtle uppercase tracking-wider">5. Web Extraction</span>
                <Badge color={webSources.length > 0 ? 'ok' : 'neutral'}>
                  {webSources.length > 0 ? 'Scraped' : 'Pending'}
                </Badge>
              </div>
              <div className="text-xs mt-3 space-y-2">
                <div>
                  <span className="text-ink-muted block text-[11px]">Domain</span>
                  <span className="font-mono text-xs">{company.website_domain || '—'}</span>
                </div>
                <div>
                  <span className="text-ink-muted block text-[11px]">Meta Extraction Status</span>
                  <span className="text-ink">{webSources.length > 0 ? 'Metadata & headers collected' : 'Run qualification to crawl homepage'}</span>
                </div>
              </div>
            </div>
            <div className="mt-4 pt-2 border-t border-line text-[11px] text-ink-subtle">
              Engine: Direct HTTP / BeautifulSoup
            </div>
          </div>

          {/* Panel 6: Discovery Origin & Proof */}
          <div className="rounded-lg border border-line bg-surface p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-ink-subtle uppercase tracking-wider">6. Discovery Origin</span>
                <Badge color="neutral">Source</Badge>
              </div>
              <div className="text-xs text-ink-muted mt-3 space-y-2">
                <div>
                  <span className="text-ink-muted block text-[11px]">Discovered Via</span>
                  <span className="font-medium text-ink">
                    {discoverySources.length > 0 ? discoverySources[0].provider.toUpperCase() : company.record_kind}
                  </span>
                </div>
                {discoverySources.length > 0 && discoverySources[0].source_url && (
                  <div>
                    <span className="text-ink-muted block text-[11px]">Source Proof URL</span>
                    <a href={discoverySources[0].source_url} target="_blank" rel="noopener noreferrer" className="text-accent-600 hover:underline truncate block font-mono">
                      {discoverySources[0].source_url}
                    </a>
                  </div>
                )}
              </div>
            </div>
            <div className="mt-4 pt-2 border-t border-line text-[11px] text-ink-subtle">
              Audit: Timestamps and raw payloads preserved
            </div>
          </div>
        </div>

        {/* Panel 7 & 8: AI Research Brief & Personalization Hook */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-2">
          <div className="lg:col-span-2 rounded-xl border border-line bg-surface p-5 shadow-xs">
            <div className="flex items-center justify-between mb-3 border-b border-line pb-3">
              <div>
                <span className="text-xs font-bold text-ink-subtle uppercase tracking-wider">7. Comprehensive AI Research Brief</span>
                <p className="text-xs text-ink-muted">Generated from corroborating sources with strict citation fidelity.</p>
              </div>
              {company.research_generated_at && (
                <span className="text-xs text-ink-subtle font-mono">
                  Groq Cloud · {formatDate(company.research_generated_at)}
                </span>
              )}
            </div>

            {company.research_brief ? (
              <div className="prose prose-sm max-w-none text-ink bg-surface-muted p-4 rounded-lg border border-line text-xs font-mono whitespace-pre-wrap max-h-96 overflow-y-auto leading-relaxed">
                {company.research_brief}
              </div>
            ) : (
              <div className="p-8 text-center bg-surface-muted rounded-lg border border-dashed border-line">
                <p className="text-sm text-ink-muted font-medium">No research brief generated yet.</p>
                <p className="text-xs text-ink-subtle mt-1 mb-4">Click "Run qualification" to invoke Groq AI and synthesize the research dossier.</p>
                <Button variant="primary" size="sm" loading={qualifying} onClick={handleRunQualification}>
                  Run qualification now
                </Button>
              </div>
            )}
          </div>

          {/* Panel 8 & 9: Sales Angle & Safety Constraints */}
          <div className="space-y-4">
            <div className="rounded-xl border border-line bg-surface p-5 shadow-xs">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-ink-subtle uppercase tracking-wider">8. Caller Opening Line</span>
                <Badge color="ok">Ready</Badge>
              </div>
              <p className="text-xs text-ink-muted mb-3">Contextualized trigger for the caller:</p>
              <div className="p-3 bg-surface-muted rounded border border-line text-xs text-ink italic leading-relaxed">
                “Hi {company.canonical_name} team, noticed your work in {company.sector || 'the B2B technology space'}{company.country ? ` in ${company.country}` : ''}. We noticed your expansion and wanted to share how we support tech companies in your stage...”
              </div>
            </div>

            <div className="rounded-xl border border-warn/30 bg-warn-bg/50 p-4 shadow-xs">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold text-warn uppercase tracking-wider">9. Compliance & Dry-Run</span>
                <Badge color="warn">NO SEND</Badge>
              </div>
              <p className="text-xs text-warn leading-relaxed mt-2">
                Backend-enforced dry-run guard active. Emails, SMS, and LinkedIn channels cannot transmit live messages.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Full Evidence Audit Log Table */}
      {sources.length > 0 && (
        <Card className="mt-2">
          <CardHeader>
            <Flex justify="between" align="center">
              <Heading size="md">Corroborated Evidence Audit Trail ({sources.length})</Heading>
              <span className="text-xs text-ink-muted">Every fact links to its retrieval proof</span>
            </Flex>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Provider</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Retrieved</TableHead>
                  <TableHead>Source URL</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sources.map((src: SourceRecord) => (
                  <TableRow key={src.id}>
                    <TableCell><Badge color="neutral">{src.provider}</Badge></TableCell>
                    <TableCell><Badge color="neutral">{src.source_type}</Badge></TableCell>
                    <TableCell><Badge color={getStatusColor(src.status)}>{src.status}</Badge></TableCell>
                    <TableCell className="text-xs">{formatDate(src.retrieved_at)}</TableCell>
                    <TableCell>
                      {src.source_url ? (
                        <a href={src.source_url} target="_blank" rel="noopener noreferrer" className="text-accent-600 hover:underline max-w-[280px] truncate block text-xs font-mono">
                          {src.source_url}
                        </a>
                      ) : <span className="text-ink-subtle">—</span>}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </Stack>
  );
}