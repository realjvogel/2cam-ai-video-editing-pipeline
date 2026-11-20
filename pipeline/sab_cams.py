"""SAB virtual camera: auto-tight base framing from papers.json + detail-zoom windows from edl.json.
cam(t) -> [z, cx, cy] in normalized source coords (t = raw top-camera seconds)."""
import json, os, numpy as np
class Cams:
    def __init__(self, ep_dir, edl):
        P=np.array(json.load(open(ep_dir+'/papers.json'))); self.n=int(P[:,0].max())+2
        T=np.arange(self.n); self.L=np.zeros((self.n,4)); self.R=np.zeros((self.n,4))
        for j in range(4):
            self.L[:,j]=np.interp(T,P[:,0],P[:,1+j]); self.R[:,j]=np.interp(T,P[:,0],P[:,5+j])
        def rm(x,k):
            p=k//2; xp=np.pad(x,(p,p),mode='edge'); return np.array([np.median(xp[i:i+k]) for i in range(len(x))])
        def av(x,k): return np.convolve(np.pad(x,(k//2,k//2),mode='edge'),np.ones(k)/k,'valid')
        for A in (self.L,self.R):
            for j in range(4): A[:,j]=av(rm(A[:,j],41),21)
        self.M=edl.get('frame_margin',0.035); self.win=edl.get('zooms',[])
        self.bmax=edl.get('base_zoom_max',9); self.zmax=edl.get('zoom_max',2.0)   # 1080p sources: cap zoom so it doesn't go soft
    def _at(self,A,t):
        i=int(min(max(t,0),self.n-2)); f=min(max(t-i,0),1); return A[i]*(1-f)+A[i+1]*f
    def base(self,t):
        l=self._at(self.L,t); r=self._at(self.R,t); x0,y0=min(l[0],r[0]),min(l[1],r[1]); x1,y1=max(l[2],r[2]),max(l[3],r[3])
        s=min(1.0,max(x1-x0+2*self.M,y1-y0+2*self.M)); h=s/2
        s=max(s,1/self.bmax); h=s/2
        return np.array([1/s,min(max((x0+x1)/2,h),1-h),min(max((y0+y1)/2,h),1-h)])
    def target(self,side,t):
        b=self._at(self.L if side=='L' else self.R,t); ph=b[3]-b[1]; z=float(np.clip(1/(0.92*ph),min(1.6,self.zmax),self.zmax))
        return np.array([z,(b[0]+b[2])/2,b[1]+0.47*ph])
    @staticmethod
    def sm(p): p=min(max(p,0),1); return p*p*(3-2*p)
    def cam(self,t):
        b=self.base(t)
        for w in self.win:   # w: {t_in, t_out, first:'L'|'R' (adult), switch: t | null, sides: [[t,side],..] (wins)}
            i0,o1=w['t_in'],w['t_out']; i1,o0=i0+1.2,o1-1.2
            if i0<=t<=o1:
                k=self.sm((t-i0)/1.2) if t<i1 else (1-self.sm((t-o0)/1.2) if t>o0 else 1)
                s1=w['first']; s2='R' if s1=='L' else 'L'; sw=w.get('switch')
                if w.get('sides'):   # [[t, side], ...] from sab_edl (adult hand tracking); glide 1.4 s at each change
                    sd=w['sides']; j=max(i for i in range(len(sd)) if sd[i][0]<=t) if t>=sd[0][0] else 0
                    cur=self.target(sd[j][1],t)
                    if j>0 and t<sd[j][0]+1.4: p=self.sm((t-sd[j][0])/1.4); D=self.target(sd[j-1][1],t)*(1-p)+cur*p
                    else: D=cur
                elif sw and t>=sw: D=self.target(s1,t)*(1-self.sm((t-sw)/1.4))+self.target(s2,t)*self.sm((t-sw)/1.4)
                else: D=self.target(s1,t)
                return b*(1-k)+D*k
        return b
