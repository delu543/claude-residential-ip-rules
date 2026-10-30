// Original routing policy. Render OPTIONS locally; never publish rendered scripts.
function build(config, o) {
  const fixed = '住宅固定节点', claude = 'Claude 固定出口';
  const normal = o.preferredPattern ? '普通外网（优先地区）' : '普通外网（美国优先）';
  const us = o.preferredPattern ? '普通·优先地区' : '普通·美国', other = '普通·其他地区';
  const preferredPattern = o.preferredPattern || o.usPattern;
  const gpt = o.chatgptResidential === true ? 'ChatGPT 住宅出口' : 'ChatGPT 普通出口';
  const provider = 'ordinary-only';
  const clone = x => JSON.parse(JSON.stringify(x));
  config = clone(config);
  const candidates = (config.proxies || []).filter(p =>
    p.name === o.residential.name && p.server === o.residential.server &&
    p.port === o.residential.port && p.type === o.residential.type);
  // A missing/renamed entrance becomes REJECT. Throwing in a Verge extension
  // alone is insufficient: some versions skip failed extensions.
  const node = candidates.length === 1 ? {...candidates[0], name: fixed} : {name: fixed, type: 'reject'};
  if (node['dialer-proxy']) throw new Error('Chained residential entrance needs a separate reviewed setup');
  config.proxies = [...(config.proxies || []).filter(p => p.name !== fixed), node];
  config['proxy-providers'] = {...(config['proxy-providers'] || {}), [provider]: clone(o.ordinaryProvider)};
  const health = {type: 'fallback', url: 'https://www.gstatic.com/generate_204',
    interval: 180, timeout: 4000, 'max-failed-times': 2, 'expected-status': 204, lazy: false};
  config['proxy-groups'] = [
    {name: claude, type: 'select', proxies: [fixed]},
    {name: gpt, type: 'select', proxies: [o.chatgptResidential === true ? fixed : normal]},
    // REJECT is first so that an all-dead set never resolves to DIRECT/COMPATIBLE.
    {name: normal, ...health, proxies: ['REJECT', us, other]},
    {name: us, ...health, proxies: ['REJECT'], use: [provider], filter: preferredPattern},
    {name: other, ...health, proxies: ['REJECT'], use: [provider], 'exclude-filter': preferredPattern}
  ];
  config.mode = 'rule';
  config['find-process-mode'] = 'always';
  const pathPattern = paths => (o.platform === 'win32' ? '(?i)' : '') + '^(?:' + paths.map(p => {
    const escaped = p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    // Directory entries carry a separator; executable entries match exactly.
    return escaped + (/[\\/]$/.test(p) ? '' : '$');
  }).join('|') + ')';
  const cp = o.claudePaths?.length ? pathPattern(o.claudePaths) : null;
  const xp = o.codexPaths?.length ? pathPattern(o.codexPaths) : null;
  const directCountries = o.directCountries || ['CN'];
  const directGeosites = o.directGeosites || (directCountries.includes('CN') ? ['cn'] : []);
  // Verge cannot read files: manage.py embeds this same policy in rendered scripts.
  const policy = typeof ROUTING_POLICY !== 'undefined' ? ROUTING_POLICY : require('./policy.json');
  const claudeDomains = policy.claudeDomains;
  const openaiDomains = policy.openaiDomains;
  const hosts = '(OR,(' + openaiDomains.map(d => `(DOMAIN-SUFFIX,${d})`).join(',') + '))';
  config.rules = [
    ...(cp ? [`AND,((NETWORK,udp),(PROCESS-PATH-REGEX,${cp})),REJECT`,
    `AND,((PROCESS-PATH-REGEX,${cp}),(NOT,((GEOIP,private)))),${claude}`] : []),
    ...claudeDomains.map(d => `DOMAIN-SUFFIX,${d},${claude}`),
    'GEOSITE,PRIVATE,DIRECT', 'DOMAIN-SUFFIX,localhost,DIRECT', 'DOMAIN-SUFFIX,local,DIRECT',
    'GEOIP,PRIVATE,DIRECT,no-resolve',
    ...(xp ? [`AND,((PROCESS-PATH-REGEX,${xp}),${hosts}),${normal}`] : []),
    ...openaiDomains.map(d => `DOMAIN-SUFFIX,${d},${gpt}`),
    ...['GOOGLE', 'YOUTUBE', 'TELEGRAM', 'NETFLIX'].map(s => `GEOSITE,${s},${normal}`),
    ...(o.directDomains || (directCountries.includes('CN') ? ['bilibili.com','bilivideo.com','douyu.com','douyucdn.cn','gov.cn'] : [])).map(d => `DOMAIN-SUFFIX,${d},DIRECT`),
    ...(directCountries.includes('CN') ? [`GEOSITE,geolocation-!cn,${normal}`] : []),
    ...directGeosites.map(t => `GEOSITE,${t.toUpperCase()},DIRECT`),
    ...directCountries.map(c => `GEOIP,${c},DIRECT,no-resolve`), `MATCH,${normal}`
  ];
  const existing = config.listeners || [];
  if (existing.some(l => l.port === o.port && l.name !== 'claude-only-http'))
    throw new Error('Dedicated port conflicts with another listener');
  config.listeners = [...existing.filter(l => l.name !== 'claude-only-http'),
    {name: 'claude-only-http', type: 'http', listen: '127.0.0.1', port: o.port, proxy: fixed}];
  const direct = (o.directResolvers || ['https://dns.alidns.com/dns-query','https://doh.pub/dns-query']).map(s => s.endsWith('#DIRECT') ? s : s + '#DIRECT');
  const upstream = o.proxiedResolvers || ['https://1.1.1.1/dns-query','https://8.8.8.8/dns-query'];
  config.dns = {...(config.dns || {}), enable: true, 'prefer-h3': false, 'respect-rules': false,
    'default-nameserver': clone(o.defaultNameservers || ['223.5.5.5', '119.29.29.29']),
    'proxy-server-nameserver': clone(o.proxyServerNameservers),
    'direct-nameserver': direct, 'direct-nameserver-follow-policy': false,
    nameserver: upstream.map(s => `${s}#${normal}`), fallback: [],
    'nameserver-policy': {'geosite:private': direct, ...Object.fromEntries(directGeosites.map(t => ['geosite:' + t, direct])),
      ...Object.fromEntries(claudeDomains.map(d => ['+.' + d, upstream.map(s => `${s}#${claude}`)])),
      ...Object.fromEntries(openaiDomains.map(d => ['+.' + d, upstream.map(s => `${s}#${o.chatgptResidential === true ? claude : normal}`)]))}};
  if (o.platform === 'win32') {
    // Never force TUN on from a profile script: GUI off must stay off.
    if (config.tun?.enable && o.windowsDnsProtection === true) {
      config.tun['auto-route'] = true;
      config.tun['strict-route'] = true;
      config.dns['enhanced-mode'] = 'fake-ip';
      config.dns['fake-ip-range'] = '198.18.0.1/16';
    }
  }
  // Cover both DNS transports without enabling/restarting TUN implicitly.
  if (config.tun?.enable) config.tun['dns-hijack'] = [...new Set([...(config.tun['dns-hijack'] || []), 'any:53', 'tcp://any:53'])];
  return config;
}
if (typeof module !== 'undefined') module.exports = {build};
