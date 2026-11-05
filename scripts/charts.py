"""Deck charts (matplotlib). Palette validated: today #2F6BC2, Ek Baithak #E1121B; ink greys for text."""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
D = json.load(open("deck/data.json", encoding="utf-8"))
OUT = "deck/charts"; os.makedirs(OUT, exist_ok=True)
INK, INK2, MUTED, GRID = "#16181d", "#4a4f59", "#8a909c", "#e7e8ec"
BLUE, RED, NEUTRAL = "#2F6BC2", "#E1121B", "#c4c8cf"
plt.rcParams.update({"font.family": "Segoe UI", "font.size": 11, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False})
STAGES = ["Leads", "Contacted", "Needs assessed", "Quote accepted", "KYC complete", "Activated"]

# 1. Funnel today (single series, steepest drop emphasised)
fig, ax = plt.subplots(figsize=(5.6, 3.3), dpi=220)
vals = D["funnel"]; pp = D["pct_prev"]
colors = [NEUTRAL] * 6; colors[3] = RED
y = list(range(6))[::-1]
ax.barh(y, vals, color=colors, height=0.62)
for yi, v, p, s in zip(y, vals, pp, STAGES):
    ax.text(-80, yi, s, ha="right", va="center", color=INK, fontsize=10.5)
    ax.text(v + 60, yi, f"{v:,}" + (f"   {p:.0%} of previous" if p else ""), va="center", color=INK, fontsize=10,
            fontweight="bold" if s == "Quote accepted" else "normal")
ax.set_xlim(0, 7600); ax.set_yticks([]); ax.set_xticks([]); ax.spines["left"].set_visible(False); ax.spines["bottom"].set_visible(False)
fig.tight_layout(pad=0.2); fig.savefig(f"{OUT}/funnel_today.png", transparent=True); plt.close(fig)

# 2. Churn vs status calls (single series)
cv = D["calls_vs_churn"]
fig, ax = plt.subplots(figsize=(4.2, 2.5), dpi=220)
xs = [c["calls"] for c in cv]; ys = [c["churn"] * 100 for c in cv]
ax.bar(xs, ys, color=[NEUTRAL, NEUTRAL, NEUTRAL, NEUTRAL, RED], width=0.6)
for x_, y_ in zip(xs, ys):
    ax.text(x_, y_ + 0.8, f"{y_:.0f}%", ha="center", color=INK, fontsize=10)
ax.set_xticks(xs); ax.set_xticklabels([f"{x} call{'s' if x > 1 else ''}" for x in xs], fontsize=9.5)
ax.set_yticks([]); ax.spines["left"].set_visible(False); ax.set_ylim(0, 33)
ax.set_title("6-month churn by status calls the customer made", fontsize=10.5, color=INK2, loc="left")
fig.tight_layout(pad=0.3); fig.savefig(f"{OUT}/churn_calls.png", transparent=True); plt.close(fig)

# 3. Funnel today vs projected (two series + legend + direct labels on last stage)
fig, ax = plt.subplots(figsize=(5.8, 3.4), dpi=220)
today, base, cons = D["sim"]["today"], D["sim"]["base"], D["sim"]["cons"]
import numpy as np
yy = np.arange(6)[::-1]
ax.barh(yy + 0.19, today, height=0.36, color=BLUE, label="Today (last quarter)")
ax.barh(yy - 0.19, base, height=0.36, color=RED, label="With Ek Baithak (base case)")
for yi, t, b, c, s in zip(yy, today, base, cons, STAGES):
    ax.text(-60, yi, s, ha="right", va="center", color=INK, fontsize=10)
    ax.text(t + 50, yi + 0.19, f"{t:,}", va="center", color=INK2, fontsize=9)
    ax.text(b + 50, yi - 0.19, f"{b:,}" + (f"  (careful case {c:,})" if s == "Activated" else ""), va="center", color=INK, fontsize=9,
            fontweight="bold" if s == "Activated" else "normal")
ax.set_xlim(0, 7000); ax.set_yticks([]); ax.set_xticks([]); ax.spines["left"].set_visible(False); ax.spines["bottom"].set_visible(False)
ax.legend(loc="lower right", frameon=False, fontsize=9.5)
fig.tight_layout(pad=0.2); fig.savefig(f"{OUT}/funnel_projected.png", transparent=True); plt.close(fig)
print("charts ok")
