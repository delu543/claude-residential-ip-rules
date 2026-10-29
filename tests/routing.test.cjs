const {test} = require('node:test');
const assert = require('node:assert/strict');
const {build} = require('../src/routing.js');
const options = require('../examples/settings.example.json');
function fixture() {
  const o = structuredClone(options);
  o.claudePaths = ['/Applications/Claude.app/', '/Users/test/.local/share/claude/versions/'];
  o.codexPaths = ['/Applications/Codex.app/'];
  return {o, c: {proxies: [{...o.residential, uuid: 'fixture-only'}],
    tun: {enable: false}, dns: {'fake-ip-filter': ['*.local']},
    listeners: [{name: 'unrelated', type: 'http', port: 18080, listen: '127.0.0.1'}]}};
}
test('ordinary group references only ordinary provider, with US before other regions', () => {
  const {c,o}=fixture(); const r=build(c,o); const groups=r['proxy-groups'];
  assert.deepEqual(groups[2].proxies, ['REJECT','普通·美国','普通·其他地区']);
  for (const g of groups.slice(3)) {assert.deepEqual(g.use,['ordinary-only']); assert.deepEqual(g.proxies,['REJECT']);}
  assert.equal(groups[3].filter, groups[4]['exclude-filter']);
  for(const g of groups.slice(2)) assert.ok(!JSON.stringify(g).includes('住宅'));
});
test('residential selector has exactly one destination; listener pins same node', () => {
  const {c,o}=fixture(), r=build(c,o);
  for(const g of r['proxy-groups'].slice(0,1)) {assert.equal(g.type,'select');assert.deepEqual(g.proxies,['住宅固定节点']);}
  assert.equal(r.listeners.at(-1).proxy,'住宅固定节点');
  assert.equal(r.listeners.at(-1).listen,'127.0.0.1');
});
test('missing, renamed, duplicate or moved residential entrance becomes reject', () => {
  for(const change of [c=>c.proxies=[], c=>c.proxies[0].server='192.0.2.99',
    c=>c.proxies[0].name='renamed', c=>c.proxies.push({...c.proxies[0]})]) {
    const {c,o}=fixture(); change(c);
    assert.equal(build(c,o).proxies.find(p=>p.name==='住宅固定节点').type,'reject');
  }
});
test('rules prioritize Claude and Codex process before generic ChatGPT', () => {
  const {c,o}=fixture(),r=build(c,o),rules=r.rules;
  assert.ok(rules[0].endsWith(',REJECT'));
  const codex=rules.findIndex(x=>x.includes('Codex'));
  assert.ok(codex<rules.findIndex(x=>x==='DOMAIN-SUFFIX,chatgpt.com,ChatGPT 普通出口'));
  assert.equal(rules.at(-1),'MATCH,普通外网（美国优先）');
  assert.ok(rules.includes('GEOSITE,CN,DIRECT'));
  assert.ok(rules.includes('DOMAIN-SUFFIX,claudeusercontent.com,Claude 固定出口'));
});
test('preserves TUN, other listener and fake IP exclusions; deterministic/idempotent', () => {
  const {c,o}=fixture(), original=structuredClone(c), r=build(c,o);
  assert.deepEqual(c,original); assert.deepEqual(r.tun,c.tun);
  assert.deepEqual(r.dns['fake-ip-filter'],['*.local']);
  assert.deepEqual(r.listeners[0],c.listeners[0]); assert.deepEqual(build(r,o),r);
});
test('independent node DNS; residential domain DNS routed explicitly', () => {
  const {c,o}=fixture(),r=build(c,o);
  assert.deepEqual(r.dns['proxy-server-nameserver'],o.proxyServerNameservers);
  assert.deepEqual(r.dns['nameserver-policy']['+.claude.ai'],['https://1.1.1.1/dns-query#Claude 固定出口']);
});
test('port collision and unreviewed chain do not silently override', () => {
  const {c,o}=fixture(); c.listeners[0].port=o.port; assert.throws(()=>build(c,o),/conflicts/);
  c.listeners=[];c.proxies[0]['dialer-proxy']='another';assert.throws(()=>build(c,o),/Chained/);
});

test('only Claude uses residential by default; ChatGPT opt-in remains explicit', () => {
  const {c,o}=fixture(); const r=build(c,o);
  assert.deepEqual(r['proxy-groups'][1].proxies,['普通外网（美国优先）']);
  assert.deepEqual(r.dns['nameserver-policy']['+.openai.com'],['https://1.1.1.1/dns-query#普通外网（美国优先）']);
  o.chatgptResidential=true;const legacy=build(c,o);
  assert.deepEqual(legacy['proxy-groups'][1].proxies,['住宅固定节点']);
  assert.ok(legacy.rules.includes('DOMAIN-SUFFIX,chatgpt.com,ChatGPT 住宅出口'));
});
test('enabled TUN captures UDP and TCP DNS and retains unrelated options', () => {
  const {c,o}=fixture();c.tun={enable:true,stack:'gvisor','dns-hijack':['any:53']};
  const r=build(c,o);assert.deepEqual(r.tun['dns-hijack'],['any:53','tcp://any:53']);
  assert.equal(r.tun.stack,'gvisor');assert.deepEqual(build(r,o),r);
});
