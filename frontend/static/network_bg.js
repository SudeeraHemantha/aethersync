// Cyberpunk P2P Particle Network Engine
const canvas = document.getElementById('network-bg');
const ctx = canvas.getContext('2d');

let width = canvas.width = window.innerWidth;
let height = canvas.height = window.innerHeight;

const particles = [];
const pings = [];
const bursts = [];
const maxParticles = Math.min(60, Math.floor((width * height) / 25000)); // Responsive count
const connectionDist = 120;
let mouse = { x: null, y: null, active: false };

class Particle {
    constructor() {
        this.reset();
        this.y = Math.random() * height; // initial spread
    }

    reset() {
        this.x = Math.random() * width;
        this.y = Math.random() > 0.5 ? -10 : height + 10;
        this.vx = (Math.random() - 0.5) * 0.4;
        this.vy = (Math.random() - 0.5) * 0.4;
        this.size = Math.random() * 2 + 1;
        this.alpha = Math.random() * 0.4 + 0.2;
    }

    update() {
        // Move
        this.x += this.vx;
        this.y += this.vy;

        // Attract to mouse
        if (mouse.active && mouse.x !== null) {
            const dx = mouse.x - this.x;
            const dy = mouse.y - this.y;
            const dist = Math.hypot(dx, dy);
            if (dist < 200) {
                const force = (200 - dist) / 2000;
                this.vx += (dx / dist) * force * 0.15;
                this.vy += (dy / dist) * force * 0.15;
            }
        }

        // Limit velocity
        const speed = Math.hypot(this.vx, this.vy);
        if (speed > 1.2) {
            this.vx = (this.vx / speed) * 1.2;
            this.vy = (this.vy / speed) * 1.2;
        }

        // Wrap or reset boundaries
        if (this.x < -20 || this.x > width + 20 || this.y < -20 || this.y > height + 20) {
            this.reset();
        }
    }

    draw() {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(59, 130, 246, ${this.alpha})`;
        ctx.fill();
    }
}

class Ping {
    constructor(x, y) {
        this.x = x;
        this.y = y;
        this.radius = 0;
        this.maxRadius = 150;
        this.speed = 4;
        this.alpha = 1;
    }

    update() {
        this.radius += this.speed;
        this.alpha = Math.max(0, 1 - (this.radius / this.maxRadius));
        return this.radius < this.maxRadius;
    }

    draw() {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(239, 68, 68, ${this.alpha * 0.4})`;
        ctx.lineWidth = 2;
        ctx.stroke();
    }
}

class BurstParticle {
    constructor(x, y) {
        this.x = x;
        this.y = y;
        const angle = Math.random() * Math.PI * 2;
        const speed = Math.random() * 3 + 1;
        this.vx = Math.cos(angle) * speed;
        this.vy = Math.sin(angle) * speed - 1.5; // fly upwards slightly
        this.size = Math.random() * 2 + 1;
        this.alpha = 1;
        this.life = 1;
        this.decay = Math.random() * 0.02 + 0.01;
    }

    update() {
        this.x += this.vx;
        this.y += this.vy;
        this.vy += 0.04; // gravity drift
        this.life -= this.decay;
        this.alpha = Math.max(0, this.life);
        return this.life > 0;
    }

    draw() {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(6, 182, 212, ${this.alpha})`; // Cyan burst
        ctx.shadowBlur = 4;
        ctx.shadowColor = '#06b6d4';
        ctx.fill();
        ctx.shadowBlur = 0; // reset shadow
    }
}

// Initialize particles
for (let i = 0; i < maxParticles; i++) {
    particles.push(new Particle());
}

// Window resize
window.addEventListener('resize', () => {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
});

// Cursor Tracking
window.addEventListener('mousemove', (e) => {
    mouse.x = e.clientX;
    mouse.y = e.clientY;
    mouse.active = true;
});

window.addEventListener('mouseleave', () => {
    mouse.active = false;
});

// Touch Tracking
window.addEventListener('touchmove', (e) => {
    if (e.touches.length > 0) {
        mouse.x = e.touches[0].clientX;
        mouse.y = e.touches[0].clientY;
        mouse.active = true;
    }
}, { passive: true });

window.addEventListener('touchend', () => {
    mouse.active = false;
});

// Click Radar Ripple
window.addEventListener('click', (e) => {
    // Ignore clicks on buttons/inputs to avoid cluttering normal UI clicks
    if (e.target.tagName === 'BUTTON' || e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        return;
    }
    pings.push(new Ping(e.clientX, e.clientY));

    // Push particles away from ping
    particles.forEach(p => {
        const dx = p.x - e.clientX;
        const dy = p.y - e.clientY;
        const dist = Math.hypot(dx, dy);
        if (dist < 150) {
            const force = (150 - dist) / 10;
            p.vx += (dx / dist) * force;
            p.vy += (dy / dist) * force;
        }
    });
});

// Public trigger function for Send Message particle bursts
window.triggerSendBurst = function(x, y) {
    for (let i = 0; i < 20; i++) {
        bursts.push(new BurstParticle(x, y));
    }
};

// Main loop
function animate() {
    ctx.clearRect(0, 0, width, height);

    // 1. Update and draw particles
    particles.forEach(p => {
        p.update();
        p.draw();
    });

    // 2. Draw connections between close particles
    for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
            const dx = particles[i].x - particles[j].x;
            const dy = particles[i].y - particles[j].y;
            const dist = Math.hypot(dx, dy);
            if (dist < connectionDist) {
                const alpha = (1 - (dist / connectionDist)) * 0.15;
                ctx.beginPath();
                ctx.moveTo(particles[i].x, particles[i].y);
                ctx.lineTo(particles[j].x, particles[j].y);
                ctx.strokeStyle = `rgba(59, 130, 246, ${alpha})`;
                ctx.lineWidth = 0.5;
                ctx.stroke();
            }
        }
    }

    // 3. Update and draw radar pings
    for (let i = pings.length - 1; i >= 0; i--) {
        const active = pings[i].update();
        if (active) {
            pings[i].draw();
        } else {
            pings.splice(i, 1);
        }
    }

    // 4. Update and draw message bursts
    for (let i = bursts.length - 1; i >= 0; i--) {
        const active = bursts[i].update();
        if (active) {
            bursts[i].draw();
        } else {
            bursts.splice(i, 1);
        }
    }

    requestAnimationFrame(animate);
}

// Start
animate();
