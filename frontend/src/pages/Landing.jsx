import { Link } from 'react-router-dom'
import { Icon } from '../icons'

const FEATURES = [
  {
    icon: '💬',
    tone: { background: 'var(--accent-soft)', color: 'var(--accent)' },
    title: 'Threaded posts',
    desc: 'Post, reply, and quote in real threads — every reply is a first-class post with its own replies and comments.',
  },
  {
    icon: '🎙️',
    tone: { background: '#eee9fd', color: 'var(--violet)' },
    title: 'Live audio & video',
    desc: 'Spin up a Space in seconds. Speakers, listeners, and an in-room chat, all in one place.',
  },
  {
    icon: '❤️',
    tone: { background: '#fff2df', color: '#c17a06' },
    title: 'Likes that mean it',
    desc: 'Like posts and comments, follow threads, and see what your circle is actually talking about.',
  },
  {
    icon: '🔒',
    tone: { background: '#e7f7ef', color: 'var(--success)' },
    title: 'Moderation built in',
    desc: 'Report a post or a room in two taps — a real review workflow, not a black hole.',
  },
  {
    icon: '🧵',
    tone: { background: '#fde8ea', color: '#c8384c' },
    title: 'DMs & group chats',
    desc: 'Private threads live right alongside Spaces — one inbox for live rooms and quiet conversations.',
  },
  {
    icon: '⚡',
    tone: { background: '#e5f1fd', color: '#1c6fd6' },
    title: 'Built to move fast',
    desc: 'A lean API underneath means the feed, the replies, and the room chat all feel instant.',
  },
]

const STEPS = [
  { n: '01', title: 'Make an account', desc: 'Sign up in under a minute — just the basics, no fifteen-step wizard.' },
  { n: '02', title: 'Say something', desc: 'Post a thought, attach a photo, or jump straight into a live Space.' },
  { n: '03', title: 'Find your people', desc: 'Reply, like, and follow threads until your feed feels like yours.' },
]

export default function Landing() {
  return (
    <div>
      <header className="landing-nav">
        <div className="landing-logo">
          <span className="mark" />
          Yipi
        </div>
        <div className="row gap-3">
          <Link to="/login" className="btn btn-ghost btn-sm">
            Log in
          </Link>
          <Link to="/signup" className="btn btn-brand btn-sm">
            Sign up free
          </Link>
        </div>
      </header>

      <section className="landing-hero">
        <div className="landing-hero-inner">
          <div>
            <span className="landing-eyebrow">
              <Icon.Sparkle size={14} /> Now with live Spaces
            </span>
            <h1>
              Talk, post, and go <em>live</em> with people who get you.
            </h1>
            <p className="lede">
              Yipi is the social feed and the group chat and the live room, all in one place —
              built for conversations that actually go somewhere.
            </p>
            <div className="landing-cta-row">
              <Link to="/signup" className="btn btn-brand">
                Create your account
              </Link>
              <Link to="/login" className="btn btn-ghost">
                I already have one
              </Link>
            </div>
            <div className="landing-stats">
              <div className="stat">
                <b>threaded</b>
                <span>every reply, its own thread</span>
              </div>
              <div className="stat">
                <b>live</b>
                <span>audio & video Spaces</span>
              </div>
              <div className="stat">
                <b>moderated</b>
                <span>reports that get reviewed</span>
              </div>
            </div>
          </div>

          <div className="hero-mock" aria-hidden="true">
            <div className="mock-post">
              <div className="mock-row">
                <span className="avatar avatar-sm" style={{ background: 'var(--gradient-brand)' }} />
                <div className="stack gap-1" style={{ flex: 1 }}>
                  <div className="mock-line" style={{ width: '38%' }} />
                  <div className="mock-line" style={{ width: '22%', opacity: 0.6 }} />
                </div>
              </div>
              <div className="mock-line" style={{ width: '92%' }} />
              <div className="mock-line" style={{ width: '70%' }} />
              <div className="mock-actions">
                <Icon.Heart size={16} />
                <Icon.Comment size={16} />
                <Icon.Repeat size={16} />
              </div>
            </div>
            <div className="mock-live">
              <div>
                <div className="row gap-2" style={{ marginBottom: 6 }}>
                  <span className="badge badge-live" style={{ background: 'rgba(255,255,255,0.15)', color: '#fff' }}>
                    Live
                  </span>
                </div>
                <div style={{ fontWeight: 700 }}>Friday night wind-down</div>
                <div style={{ fontSize: '0.78rem', opacity: 0.75 }}>82 listening</div>
              </div>
              <div className="avatars">
                <span className="avatar avatar-sm" style={{ background: 'hsl(20 80% 60%)' }} />
                <span className="avatar avatar-sm" style={{ background: 'hsl(260 70% 65%)' }} />
                <span className="avatar avatar-sm" style={{ background: 'hsl(150 60% 45%)' }} />
              </div>
            </div>
            <div className="mock-post">
              <div className="mock-row">
                <span className="avatar avatar-sm" style={{ background: 'hsl(200 70% 55%)' }} />
                <div className="stack gap-1" style={{ flex: 1 }}>
                  <div className="mock-line" style={{ width: '30%' }} />
                </div>
              </div>
              <div className="mock-line" style={{ width: '60%' }} />
            </div>
          </div>
        </div>
      </section>

      <section className="landing-section">
        <div className="section-heading">
          <span className="kicker">Everything in one feed</span>
          <h2>One app for every kind of conversation</h2>
          <p>Posts, replies, comments, DMs, and live Spaces — Yipi doesn't make you pick one.</p>
        </div>
        <div className="feature-grid">
          {FEATURES.map((f) => (
            <div className="feature-card" key={f.title}>
              <div className="icon-tile" style={f.tone}>
                {f.icon}
              </div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="landing-section">
        <div className="landing-showcase">
          <div className="showcase-list">
            {STEPS.map((s) => (
              <div className="showcase-item" key={s.n}>
                <span className="num">{s.n}</span>
                <div>
                  <h4>{s.title}</h4>
                  <p>{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="showcase-visual">
            <div className="mock-live" style={{ marginBottom: 12 }}>
              <div>
                <div style={{ fontWeight: 700 }}>Design chat</div>
                <div style={{ fontSize: '0.78rem', opacity: 0.75 }}>3 people in this room</div>
              </div>
              <Icon.Radio size={22} />
            </div>
            <div className="mock-post">
              <div className="mock-row">
                <span className="avatar avatar-sm" style={{ background: 'hsl(340 75% 60%)' }} />
                <div className="stack gap-1" style={{ flex: 1 }}>
                  <div className="mock-line" style={{ width: '40%' }} />
                </div>
              </div>
              <div className="mock-line" style={{ width: '85%' }} />
              <div className="mock-line" style={{ width: '55%' }} />
            </div>
          </div>
        </div>
      </section>

      <section className="landing-section">
        <div className="cta-band">
          <h2>Your feed is waiting.</h2>
          <p>Join Yipi and start a thread, a room, or just say hello.</p>
          <Link to="/signup" className="btn btn-brand">
            Sign up — it's free
          </Link>
        </div>
      </section>

      <footer className="landing-footer">
        <div className="landing-logo">
          <span className="mark" />
          Yipi
        </div>
        <div className="links">
          <Link to="/login">Log in</Link>
          <Link to="/signup">Sign up</Link>
        </div>
      </footer>
    </div>
  )
}
