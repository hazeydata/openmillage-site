"""BEEHIIV-104 Phase 4: newsletter signup copy/accessibility (generator) and the built homepage. Run: python3 -m pytest -q tests/test_newsletter.py
Needs docs/ built (python3 build.py). The JS controller is tested by tests/newsletter.test.js (node --test), also run from here."""
import os, re, shutil, subprocess, sys, unittest
from html.parser import HTMLParser
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import redo

class P(HTMLParser):
    def __init__(s): super().__init__(); s.tags = []
    def handle_starttag(s, t, a): s.tags.append((t, dict(a)))
def parse(h): p = P(); p.feed(h); return p.tags
def by(tags, t, **kw): return [a for n, a in tags if n == t and all(a.get(k) == v for k, v in kw.items())]

class Generator(unittest.TestCase):
    def test_copy_exact(self):
        c = redo.NEWSLETTER_COPY; h = redo.newsletter()
        self.assertEqual(c["heading"], "OpenMillage updates from HazeyData")
        self.assertEqual(c["description"], "Join the HazeyData newsletter. We tag you for OpenMillage. Same list covers our other public-data products.")
        self.assertEqual((c["label"], c["button"]), ("Email", "Get updates"))
        self.assertEqual(c["success"], "You're on the list."); self.assertEqual(c["invalid"], "That email doesn't look right. Try again.")
        self.assertEqual(c["already"], "You're already on the list."); self.assertEqual(c["pending"], "Your subscription is pending confirmation.")
        self.assertEqual(c["sending"], "Sending…")
        self.assertIn("Something broke on our end. Try again in a minute, or email <a href='mailto:fred@hazeydata.ai'>fred@hazeydata.ai</a></template>", h)
        for s in ("<h2 id=newsletter-h>OpenMillage updates from HazeyData</h2>", ">Email</label>", ">Get updates</button>"): self.assertIn(s, h)
    def test_form_contract_and_a11y(self):
        t = parse(redo.newsletter())
        f = by(t, "form")[0]
        self.assertEqual((f["method"], f["action"]), ("post", "https://hazeydata.ai/api/subscribe"))
        self.assertEqual(by(t, "input", name="source")[0]["value"], "openmillage")
        self.assertTrue(by(t, "input", name="website")[0]["tabindex"] == "-1")
        em = by(t, "input", type="email")[0]; self.assertEqual(em["id"], "newsletter-email")
        self.assertEqual(by(t, "label", **{"for": "newsletter-email"}) and 1, 1)
        st = by(t, "p", id="newsletter-status")[0]; self.assertEqual((st["role"], st["aria-live"]), ("status", "polite"))
        self.assertIn("callout", by(t, "section")[0]["class"]); self.assertEqual(by(t, "section")[0]["aria-labelledby"], "newsletter-h")
    def test_rendered_data_msgs_carry_final_copy(self):
        c = redo.NEWSLETTER_COPY; f = by(parse(redo.newsletter()), "form")[0]
        for k in ("success", "already", "pending", "sending", "invalid"): self.assertEqual(f["data-msg-" + k], c[k], k)
        self.assertEqual(f["data-endpoint"], "https://hazeydata.ai/api/subscribe")
    def test_no_promises(self):
        txt = re.sub(r"<[^>]+>", " ", redo.newsletter()).lower()
        for w in ("weekly", "daily", "monthly", "confirmation email", "check your inbox", "unsubscribe", "never spam"): self.assertNotIn(w, txt)

class Built(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(os.path.join(ROOT, "docs/index.html")): raise unittest.SkipTest("docs/ not built")
        cls.h = open(os.path.join(ROOT, "docs/index.html"), encoding="utf-8").read()
    def test_homepage_has_form_once_before_get_data(self):
        self.assertEqual(self.h.count("id=newsletter-form"), 1)
        self.assertEqual(self.h.count("<script src='/newsletter.js' defer>"), 1)
        self.assertLess(self.h.index("id=newsletter-form"), self.h.index("id=get-the-data"))
        self.assertIn(redo.newsletter(), self.h)
    def test_built_form_data_msgs_match_final_copy(self):
        c = redo.NEWSLETTER_COPY; f = by(parse(self.h), "form", id="newsletter-form")[0]
        for k in ("success", "already", "pending", "sending", "invalid"): self.assertEqual(f["data-msg-" + k], c[k], k)
    def test_support_address_is_in_footer(self):
        self.assertIn("<a href='mailto:fred@hazeydata.ai'>fred@hazeydata.ai</a>", self.h.split("<footer>")[1])
    def test_asset_copied_identically(self):
        self.assertEqual(open(os.path.join(ROOT, "docs/newsletter.js"), "rb").read(), open(os.path.join(ROOT, "assets/newsletter.js"), "rb").read())
    def test_only_homepage_has_form(self):
        n = [os.path.join(d, f) for d, _, fs in os.walk(os.path.join(ROOT, "docs")) for f in fs if f.endswith(".html") and "newsletter-form" in open(os.path.join(d, f), encoding="utf-8").read()]
        self.assertEqual([os.path.relpath(p, ROOT) for p in n], ["docs/index.html"])

class JS(unittest.TestCase):
    def test_node_controller(self):
        node = shutil.which("node")
        if not node: self.skipTest("node not installed")
        r = subprocess.run([node, "--test", "tests/newsletter.test.js"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

if __name__ == "__main__": unittest.main()
