import numpy as np, time
W,H,U,G=1280,720,50.0,3
def roots(F):
    xs=(np.arange(0,W+G,G)-W/2+0.5)/U; ys=-(np.arange(0,H+G,G)-H/2+0.5)/U
    X,Y=np.meshgrid(xs,ys)
    with np.errstate(all='ignore'):
        V=np.broadcast_to(np.asarray(F(X,Y),float),X.shape)
        pts=[]
        for (ax,ay,bx,by,va,vb) in [(X[:,:-1],Y[:,:-1],X[:,1:],Y[:,1:],V[:,:-1],V[:,1:]),(X[:-1],Y[:-1],X[1:],Y[1:],V[:-1],V[1:])]:
            m=np.isfinite(va)&np.isfinite(vb)&(np.sign(va)!=np.sign(vb))
            ax,ay,bx,by,va,vb=[a[m] for a in (ax,ay,bx,by,va,vb)]
            f0=np.minimum(abs(va),abs(vb))
            for _ in range(5):
                mx,my=(ax+bx)/2,(ay+by)/2; vm=F(mx,my)
                left=np.sign(vm)==np.sign(va)
                ax=np.where(left,mx,ax);ay=np.where(left,my,ay);va=np.where(left,vm,va)
                bx=np.where(left,bx,mx);by=np.where(left,by,my);vb=np.where(left,vb,vm)
            fr=np.minimum(abs(va),abs(vb))
            ok=np.isfinite(fr)&(fr<0.5*f0)
            pts.append(np.c_[(ax+bx)/2,(ay+by)/2][ok])
    return np.vstack(pts)
cases={'circle r1':lambda x,y:x**2+y**2-1,'x=2':lambda x,y:x-2+0*y,'y=tan(x)':lambda x,y:y-np.tan(x),
 'tan(r)=y/x':lambda x,y:np.tan(np.sqrt(x**2+y**2))-y/x,'y=sqrt(x)':lambda x,y:y-np.sqrt(x),'y=1/x':lambda x,y:y-1/x}
for k,F in cases.items():
    t=time.perf_counter(); P=roots(F); dt=(time.perf_counter()-t)*1000
    L=len(P)*G/U/1.27
    # pole leak check: points with |x| near 0 for y=1/x, near pi/2 for tan
    print(f"{k:12s} pts={len(P):6d} L~{L:6.1f}u  {dt:5.1f}ms", end='')
    if k=='y=tan(x)': print('  bad(on asymptote, |y|<5):',int(np.sum((abs(np.cos(P[:,0]))<0.02)&(abs(P[:,1])<5))))
    elif k=='y=1/x': print('  bad(x~0,|y|<5):',int(np.sum((abs(P[:,0])<0.05)&(abs(P[:,1])<5))))
    elif k=='tan(r)=y/x': print('  max residual:',float(np.nanmax(abs(np.tan(np.hypot(*P.T))-P[:,1]/P[:,0])/(1+abs(P[:,1]/P[:,0])))))
    else: print()
