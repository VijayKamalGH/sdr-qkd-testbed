import sys, numpy as np
sys.path.insert(0,'/home/claude/pd1'); sys.path.insert(0,'.')
import H194E_Z38_COMMON as C, H194E_V18Z37_MIMO_ANALYZE as Z, H194E_V18Z38_QKD_ANALYZE as A
import H194E_PC_KALMAN as K
for t in sys.argv[1:]:
    u=f"/mnt/user-data/uploads/H194E_V18Z34_{t}_ON"
    yks,om=K.frontend(A,Z,C,u+"_RX0.c64",u+"_RX1.c64")
    pos=np.array([n for n,_ in yks]); H=np.array([K.pilot_H(C,Z,k,om)[1] for _,k in yks]); 
    ok=np.abs(np.diff(pos)-Z.PERIOD)<=600     # consecutive frames
    v=H.reshape(len(H),4); ref=v.mean(0)
    cp=np.angle(np.sum(v*np.conj(ref),axis=1))                  # common phase vs mean channel
    d=np.angle(np.exp(1j*np.diff(cp)))[ok]
    amp=np.abs(v).sum(1); da=np.diff(np.log(amp))[ok]
    row=v[:,2]/v[:,0]; rp=np.angle(row*np.conj(row.mean())); drp=np.angle(np.exp(1j*np.diff(rp)))[ok]
    # Doppler of common phasor, uniform run
    x=np.exp(1j*cp); x=x-x.mean(); S=np.abs(np.fft.fftshift(np.fft.fft(x*np.hanning(len(x)))))**2; f=np.fft.fftshift(np.fft.fftfreq(len(x),0.048))
    print(f"{t}: frames {len(H)} consecutive {ok.mean():.2f} | dphi_common std {d.std():.3f} rad | dlog|H| std {da.std():.3f} | drow-phase std {drp.std():.3f} | common-phase line {f[np.argmax(S)]:+.2f} Hz")
    c=lambda a:(np.corrcoef(a[:-1],a[1:])[0,1])
    ph=np.unwrap(cp); lin=np.polyfit(np.arange(len(ph)),ph,1); res=ph-np.polyval(lin,np.arange(len(ph)))
    print(f"    lag-1 autocorr of dphi {c(d):+.2f} (white phase noise = -0.5, random walk = 0) | std of phase about a straight line {res.std():.2f} rad | slope {lin[0]/0.048/(2*np.pi):+.2f} Hz")
