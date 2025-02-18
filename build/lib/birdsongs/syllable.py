from .util import *
from pathlib import Path

class Syllable(object):
    #%%
    """
    Store and define a syllable and its properties
    INPUT:
        s  = signal
        fs = sampling rate
        t0 = initial time of the syllable
    """ 
    # def __getstate__(self):
    #     state = self.__dict__.copy()
    #     #del state[''] # remove the unpicklable progress attribute
    #     return state
    # def __setstate__(self, state):
    #     self.__dict__.update(state)
    #     # restore the progress from the progress integer
    #     #self.progress = make_progress(self.progress_int)

    #%%
    def __init__(self, birdsong=None, t0=0, Nt=100, llambda=1.5, NN=None, overlap=0.5, flim=(1.5e3,2e4), n_mfcc=8,
                 n_mels=4, umbral_FF=1, tlim=[], sfs=[], no_syllable=0, ide="syllable", ff_method="yin", t0_bs=None,
                 file_name="syllable", paths=None, f1f2=None, type="", BirdData=None):
        ## The bifurcation can be cahge modifying the self.f2 and self.f1 functions
        ## ------------- Bogdanov–Takens bifurcation ------------------
        if f1f2 is None:
            f1 = "ys"
            f2 = "(-alpha-beta*xs-xs**3+xs**2)*gamma**2 -(xs+1)*gamma*xs*ys"
        beta_bif, mu1_curves, f1, f2 = BifurcationODE(f1, f2)
        self.beta_bif = beta_bif
        self.mu1_curves = mu1_curves
        self.f1 = f1
        self.f2 = f2
        ## Defining motor gestures model constants, measure by Gabo Mindlin 
        self.BirdData = {"C":343, "L":0.025, "r":0.65, "Ch":1.43E-10,
                         "MG":20, "MB":1E4, "RB":5E6, "Rh":24E3}
                                   # c, L, r, c, L1, L2, r2, rd 
        if BirdData is not None: 
            for k in BirdData.keys():  self.BirdData[k] = BirdData[k]
            
        ## -------------------------------------------------------------------------------------
        self.p = lmfit.Parameters()
        # add params:   (NAME  VALUE  VARY   MIN  MAX  EXPR BRUTE_STEP)
        self.p.add_many(('a0', 0.11, False, 0.01, 0.25, None, None), 
                        ('a1',   0., False,   -2,    2, None, None), #0.05
                        ('a2',   0., False,    0,    2, None, None),
                        ('b0', -0.1, False,   -1,  0.5, None, None),  
                        ('b1',    1, False,    0,    2, None, None), 
                        ('b2',   0., False,    0,    2, None, None), 
                        ('gm',  4e4, False,  1e4,  1e5, None, None),
                        ('f0',    0, False, -1e3,  1e3, None, None))
        # -------------------------------------------------------------------        
        self.n_mfcc      = n_mfcc
        self.Nt          = Nt
        self.n_mels      = n_mels
        self.flim        = flim
        self.llambda     = llambda
        self.umbral_FF   = umbral_FF
        self.type        = type
        self.no_syllable = no_syllable
        self.ff_method   = ff_method
        
        # define a syllable by entering the amplitude array (out)
        if birdsong!=None: 
            self.birdsong   = birdsong
            self.fs         = self.birdsong.fs
            self.center     = self.birdsong.center
            self.paths      = self.birdsong.paths
            self.file_name  = self.birdsong.file_name
            self.state      = self.birdsong.state
            self.country    = self.birdsong.country
            self.umbral     = self.birdsong.umbral
            self.t0_bs      = self.birdsong.t0
            #self.s          = self.birdsong.s
            self.NN         = self.birdsong.NN
            self.flim       = self.birdsong.flim
            self.ff_method   = self.birdsong.ff_method
            #self.tlim       = self.birdsong.tlim
            s          = self.birdsong.s
            # self.win_length = self.birdsong.win_length
            # self.hop_length = self.birdsong.hop_length
            # self.no_overlap = self.birdsong.no_overlap
            #self.umbral_FF  = umbral_FF
            
        elif len(sfs)!=0:           
            s, fs           = sfs
            self.fs         = fs
            self.center     = False
            self.file_name  = file_name
            self.umbral     = 0.05
            self.paths      = paths
        if t0_bs!=None: self.t0_bs = t0_bs
        
        # ------ define syllable by time interval [tini, tend] --------
        if len(tlim)==0: 
            self.s  = sound.normalize(s, max_amp=1.0)
            self.t0 = t0
        elif len(tlim)!=0:
            self.s  = sound.normalize(s[int(tlim[0]*self.fs):int(tlim[1]*self.fs)], max_amp=1.0)
            self.t0 = tlim[0]

        self.time_s   = np.linspace(0, len(self.s)/self.fs, len(self.s))
        self.envelope = Enve(self.s, self.fs, self.Nt)
        self.T        = self.s.size/self.fs
        self.time0    = np.linspace(0, len(self.s)/self.fs, len(self.s))
        self.t_interval = np.array([self.time_s[0],self.time_s[-1]])+self.t0_bs

        if birdsong is None and NN is None: self.NN = 512
        elif birdsong is not None and NN is not None: self.NN = NN
        elif birdsong is None and NN is not None: self.NN = NN
            
        if ide!="": self.id = ide
        
        self.win_length = self.NN//2
        self.hop_length = self.NN//4
        self.no_overlap = int(overlap*self.NN)
        

        # self.win_length  = self.NN
        # self.hop_length  = self.NN//4
        # self.no_overlap  = int(overlap*self.NN)
        
        # -------------------------------------------------------------------
        # ------------- ACOUSTIC FEATURES -----------------------------------
        # -------------------------------------------------------------------
        self.stft = librosa.stft(y=self.s, n_fft=self.NN, hop_length=self.hop_length, win_length=self.NN, window='hann',
                                 center=self.center, dtype=None, pad_mode='constant')
        freqs, times, mags = librosa.reassigned_spectrogram(self.s, sr=self.fs, S=self.stft, n_fft=self.NN,
                                        hop_length=self.hop_length, win_length=self.win_length, window='hann', 
                                        center=self.center, reassign_frequencies=True, reassign_times=True,
                                        ref_power=1e-06, fill_nan=True, clip=True, dtype=None, pad_mode='constant')
        
        self.freqs   = freqs  
        self.times   = times 
        self.Sxx     = mags 
        self.Sxx_dB  = librosa.amplitude_to_db(mags, ref=np.max)
        self.FF_coef = np.abs(self.stft)
        self.freq = librosa.fft_frequencies(sr=self.fs, n_fft=self.NN) 
        self.time = librosa.times_like(X=self.stft,sr=self.fs, hop_length=self.hop_length, n_fft=self.NN) #, axis=-1
        self.time -= self.time[0]
        
        self.f_msf   = np.array([Norm(self.FF_coef[:,i]*self.freq, 1)/Norm(self.FF_coef[:,i], 1) for i in range(self.FF_coef.shape[1])])        
        
        self.centroid =  feature.spectral_centroid(y=self.s, sr=self.fs, S=np.abs(self.stft), n_fft=self.NN,
                                            hop_length=self.hop_length, freq=self.freqs, win_length=self.win_length, 
                                            window='hann',center=self.center, pad_mode='constant')[0]
        self.mfccs = feature.mfcc(y=self.s, sr=self.fs, S=self.stft, n_mfcc=self.n_mfcc, dct_type=2, norm='ortho', lifter=0)
        self.rms   = feature.rms(y=self.s, S=self.stft, frame_length=self.NN, hop_length=self.hop_length,
                                 center=self.center, pad_mode='constant')[0]
        self.s_mel = feature.melspectrogram(y=self.fs, sr=self.fs, S=self.stft, n_fft=self.NN, hop_length=self.hop_length,
                                            win_length=self.win_length, window='hann', center=self.center, pad_mode='constant', power=2.0)
       
        # pitches[..., f, t] contains instantaneous frequency at bin f, time t
        # magnitudes[..., f, t] contains the corresponding magnitudes.
        # Both pitches and magnitudes take value 0 at bins of non-maximal magnitude.
        # pitches, magnitudes = librosa.piptrack(y=self.s, sr=self.fs, S=self.stft, n_fft=self.NN, hop_length=self.hop_length,
        #                        fmin=self.flim[0], fmax=self.flim[1], threshold=0.01, win_length=self.win_length, 
        #                        center=self.center, pad_mode='constant', ref=None)
        # self.zcr = librosa.feature.zero_crossing_rate(y=self.s,frame_length=self.NN, hop_length=self.hop_length, center=self.center)
        # self.rolloff     = feature.spectral_rolloff(y=self.s, sr=self.fs, S=self.stft, n_fft=self.NN, 
        #                                             hop_length=self.hop_length, win_length=self.win_length, center=self.center,
        #                                             pad_mode='constant', freq=self.freqs, roll_percent=0.6)[0]
        # self.rolloff_min = feature.spectral_rolloff(y=self.s, sr=self.fs, S=self.stft, n_fft=self.NN, 
        #                                          hop_length=self.hop_length, win_length=self.win_length, 
        #                          center=self.center, pad_mode='constant', freq=self.freqs, roll_percent=0.2)[0]
        # self.onset_env   = onset.onset_strength(y=self.s, sr=self.fs, S=self.stft, lag=1, max_size=1, fmax=self.flim[1],
        #                                          ref=None, detrend=False, center=self.center, feature=None, aggregate=None)

#         # ----------------------- matrix  ----------------------------
#         self.contrast = feature.spectral_contrast(y=self.s, sr=self.fs, S=self.stft, n_fft=self.NN, hop_length=self.hop_length, 
#                                     win_length=self.win_length, center=self.center, pad_mode='constant', freq=self.freqs, 
#                                     fmin=self.flim[0], n_bands=4,quantile=0.02, linear=False)
#         self.s_mel    = feature.melspectrogram(y=self.s, sr=self.fs, S=self.stft, n_fft=self.NN, 
#                                        hop_length=self.hop_length, win_length=self.win_length, center=self.center, 
#                                        pad_mode='constant', power=2.0, n_mels=self.n_mels,
#                                        fmin=self.flim[0], fmax=self.flim[1])
#         self.s_sal    = librosa.salience(S=self.FF_coef, freqs=self.freqs, harmonics=[1, 2, 3, 4], weights=[1,1,1,1], 
#                                          aggregate=None, filter_peaks=True, fill_value=0, kind='linear', axis=-2)
#         self.C        = librosa.cqt(y=self.s, sr=self.fs, hop_length=self.hop_length, fmin=self.flim[0], n_bins=32, 
#                                     bins_per_octave=12, tuning=0.0, filter_scale=1, norm=1, sparsity=0.01, 
#                                     window='hann', scale=True, pad_mode='constant', dtype=None)
#         self.D        = librosa.iirt(y=self.s, sr=self.fs, win_length=self.win_length, hop_length=self.hop_length, center=self.center, 
#                          tuning=0.0, pad_mode='constant', flayout='sos')
        
#         self.pitches    = pitches
#         self.magnitudes = magnitudes
        
        # # self.features  = [energy, Ht, Hf]
        # # self.entropies = [EAS, ECU, ECV, EPS, EPS_KURT, EPS_SKEW]
        # # self.times_on = times_on
        
        # # ------------- "better method" --------------
        if self.ff_method=="pyin":
            self.FF,_,_     = pyin(self.s, fmin=self.flim[0], fmax=self.flim[1], sr=self.fs, frame_length=self.NN, 
                                   win_length=self.win_length, hop_length=self.hop_length, n_thresholds=100, beta_parameters=(2, 18), 
                                   boltzmann_parameter=2, resolution=0.1, max_transition_rate=35.92, switch_prob=0.01, 
                                   no_trough_prob=0.01, fill_na=0, center=self.center, pad_mode='constant')
        elif self.ff_method=="yin":
            self.FF = yin(self.s, fmin=self.flim[0], fmax=self.flim[1], sr=self.fs, frame_length=self.NN, 
                          win_length=self.win_length, hop_length=self.hop_length, center=self.center,
                          trough_threshold=self.umbral_FF, pad_mode='constant')
        elif self.ff_method=="both":
            self.FF2    = yin(self.s, fmin=self.flim[0], fmax=self.flim[1], sr=self.fs, frame_length=self.NN, 
                              win_length=self.win_length, hop_length=self.hop_length, center=self.center,
                              trough_threshold=self.umbral_FF, pad_mode='constant')
            self.FF,_,_ = pyin(self.s, fmin=self.flim[0], fmax=self.flim[1], sr=self.fs, frame_length=self.NN, 
                               win_length=self.win_length, hop_length=self.hop_length, n_thresholds=100, beta_parameters=(2, 18), 
                               boltzmann_parameter=2, resolution=0.1, max_transition_rate=35.92, switch_prob=0.01, 
                               no_trough_prob=0.01, fill_na=0, center=self.center, pad_mode='constant')
        elif self.ff_method=="manual":
            print("Not implemented yet.")
            pass
        
#         # # remove atypical data
#         df = pd.DataFrame(data={"FF":self.FF, "time":self.time})
#         q  = df["FF"].quantile(0.99)
#         df[df["FF"] < q]
#         q_low, q_hi = df["FF"].quantile(0.1), df["FF"].quantile(0.99)
#         df_filtered = df[(df["FF"] < q_hi) & (df["FF"] > q_low)]

#         self.timeFF   = self.time[df_filtered["FF"].index]
#         self.FF = self.FF[df_filtered["FF"].index]

        #self.timeFF = np.linspace(0,self.times[0][-1]+0.1,self.FF.size)
        self.timeFF = np.linspace(0,self.time[-1],self.FF.size)
        self.FF_fun = interp1d(self.timeFF, self.FF)
        self.SCI    = self.f_msf / self.FF_fun(self.time)
    
    #%%
    def AlphaBeta(self):
        a = np.array([self.p["a0"].value, self.p["a1"].value, self.p["a2"].value]);   
        b = np.array([self.p["b0"].value, self.p["b1"].value, self.p["b2"].value])
        
        t_1   = np.linspace(0,self.T,len(self.s))   
        t_par = np.array([np.ones(t_1.size), t_1, t_1**2])
        
        self.alpha = np.dot(a, t_par);  # lines (or parabolas)
        
        # define by same shape as fudamenta frequency
        if "syllable" in self.id: 
            poly = Polynomial.fit(self.timeFF, self.FF, deg=10)
            x, y = poly.linspace(np.size(self.s))
            self.beta  = b[0] + b[1]*(1e-4*y) + b[2]*(1e-4*y)**2   
        elif "chunck" in self.id: 
            self.beta = np.dot(b, t_par);

        return self.alpha, self.beta
            
    #%%
    def MotorGestures(self, alpha, beta, gamma, ovfs=20, prct_noise=0):  # ovfs:oversamp
        t, tmax, dt = 0, int(self.s.size)*ovfs-1, 1./(ovfs*self.fs) # t0, tmax, td
        # pback and pin vectors initialization
        pi, pb, out = np.zeros(tmax), np.zeros(tmax), np.zeros(int(self.s.size))
        # initial vector ODEs (v0), it is not too relevant
        v = 1e-4*np.array([1e2, 1e1, 1, 1, 1, 1]);  self.Vs = [v];
        # ------------- BIRD PARAMETERS -----------
        #BirdData = pd.read_csv(self.paths.auxdata/'ZonotrichiaData.csv')
        c, L, r, Ch = self.BirdData['C'], self.BirdData['L'], self.BirdData['r'], self.BirdData['Ch']
        MG, MB, RB, Rh  = self.BirdData['MG'], self.BirdData['MB'], self.BirdData['RB'], self.BirdData['Rh']
        #c, L, r, Ch, , Rh = BirdData['c'] # c, L, r, c, L1, L2, r2, rd 
        # - Trachea:
        #           r: reflection coeficient    [adimensionelss]
        #           L: trachea length           [m]
        #           c: speed of sound in media  [m/s]
        # - Beak, Glottis and OEC:
        #           CH: OEC Compliance          [m^3/Pa]
        #           MB: Beak Inertance          [Pa s^2/m^3 = kg/m^4]
        #           MG: Glottis Inertance       [Pa s^2/m^3 = kg/m^4]
        #           RB: Beak Resistance         [Pa s/m^3 = kg/m^4 s]
        #           Rh: OEC Resistence          [Pa s/m^3 = kg/m^4 s]
        # ------------------------------ ODEs -----------------------------
        def ODEs(v):
            dv, [x, y, pout, i1, i2, i3] = np.zeros(6), v  # (x, y, pout, i1, i2, i3)'
            # ----------------- direct implementation of the EDOs -----------
            # dv[0] = y
            # dv[1] = (-self.alpha[t//ovfs]-self.beta[t//ovfs]*x-x**3+x**2)*self.p["gm"].value**2 - (x**2*y+x*y)*self.p["gm"].value
            dv[0] = self.f1(x, y, alpha[t//ovfs], beta[t//ovfs], gamma)
            dv[1] = self.f2(x, y, alpha[t//ovfs], beta[t//ovfs], gamma)
            # ------------------------- trachea ------------------------
            pbold = pb[t]                                 # pressure back before
            # Pin(t) = Ay(t)+pback(t-L/C) = envelope_Signal*v[1]+pb[t-L/C/dt]
            pi[t] = (.5*self.envelope[t//ovfs])*dv[1] + pb[t-int(L/c/dt)] 
            pb[t] = -r*pi[t-int(L/c/dt)]                          # pressure back after: -rPin(t-L/C) 
            pout  = (1-r)*pi[t-int(L/c/dt)]                       # pout
            # ---------------------------------------------------------------
            dv[2] = (pb[t]-pbold)/dt                      # dpout
            dv[3] = i2
            dv[4] = -(1/Ch/MG)*i1 - Rh*(1/MB+1/MG)*i2 +(1/MG/Ch+Rh*RB/MG/MB)*i3 \
                    +(1/MG)*dv[2] + (Rh*RB/MG/MB)*pout
            dv[5] = -(MG/MB)*i2 - (Rh/MB)*i3 + (1/MB)*pout
            return dv        
        # ----------------------- Solving EDOs ----------------------
        while t < tmax: # and v[1] > -5e6:  # labia velocity not too fast
            v = rk4(ODEs, v, dt);  self.Vs.append(v)  # RK4 - step
            out[t//ovfs] = RB*v[-1]               # output signal (synthetic) 
            t += 1;
            
            # # if the bird OEC change of size in time
            # BirdData = pd.read_csv(self.paths.auxdata/'ZonotrichiaData.csv')
            # c, L, r, Ch, MG, MB, RB, Rh = BirdData['value'] # c, L, r, c, L1, L2, r2, rd 
        
        # ------------------------------------------------------------
        self.Vs = np.array(self.Vs)
        # define solution (synthetic syllable) as a Syllable object 
        synth = Syllable(Nt=self.Nt, llambda=self.llambda, NN=self.NN, overlap=0.5, file_name=self.file_name, t0_bs=self.t0_bs+self.t0,
                         paths=self.paths, flim=self.flim, sfs=[out, self.fs], umbral_FF=self.umbral_FF)
        
        synth.id    = self.id
        synth.Vs    = self.Vs
        synth.alpha = self.alpha
        synth.beta  = self.beta
        
        synth.timesVs = np.linspace(0, len(self.s)/self.fs, len(self.s)*ovfs)
        #delattr(self,"alpha"); delattr(self,"beta")

        return synth

    #%%    
    def WriteAudio(self):
        name = '{}/{}-{}-{}.wav'.format(self.paths.examples, self.file_name[:-4], self.id, self.no_syllable)
        WriteAudio(name, fs=self.fs, s=self.s)

    #%%    
    def Solve(self, p, orde=2, BirdData=None):
        self.p = p;  self.ord = orde; 
        if self.s.size < 2*self.fs/100: self.id = "chunck"
        else:                           self.id = "syllable"

        self.AlphaBeta()             # define alpha and beta parameters
        synth = self.MotorGestures(self.alpha, self.beta, self.p["gm"].value) # solve the problem and define the synthetic syllable
        synth = self.SynthScores(synth, orde=orde) # compute differences and score variables
        synth.paths = self.paths
        synth.p = self.p
        #synth.t_interval = self.t_interval
        synth.no_syllable = self.no_syllable
        synth.ff_method = self.ff_method
        synth.file_name = self.file_name[:-4] + "-synth"
        synth.FF -= self.p["f0"].value

        synth.state   = self.state
        synth.country = self.country
        synth.type = self.type
        synth.id = self.id
        synth.BirdData = self.BirdData

        if BirdData is not None: 
            for k in BirdData.keys():  synth.BirdData[k] = BirdData[k]

        return synth
    
    #%%
    def ExportMotorGestures(self):
        # ------------ export p values and alpha-beta arrays ------------
        #df_MotorGestures = pd.DataFrame(data={"time":self.time_s, "alpha":self.alpha, "beta":self.beta})
        df_MotorGestures_coef = pd.DataFrame(data=np.concatenate((list(self.p.valuesdict().values()), self.t_interval, [self.NN, self.umbral_FF, self.type, self.country, self.state])), 
                                            index=np.concatenate((list(self.p.valuesdict().keys()), ["t_ini", "t_end", "NN", "umbral_FF", "type", 'country', 'state'])), 
                                            columns=["value"])
        #name  = self.file_name[:-4] + "-"+str(self.id)+"-"+str(self.no_syllable)+"-MG.csv"
        name  = self.file_name[:-4] + "-"+str(self.id)+"-"+str(self.no_syllable)+"-MG.csv"
        #df_MotorGestures.to_csv(self.paths.MG_param / name, index=True)
        df_MotorGestures_coef.to_csv(self.paths.MG_param / name, index=True)

    #%%
    def SolveAB(self, alpha, beta, gamma, orde=2):
        self.alpha = alpha; self.beta  = beta;
        
        synth = self.MotorGestures(alpha, beta, gamma)
        synth = self.SynthScores(synth, orde=orde)
        synth.id = "synth-birdsongs"
        
        return synth
    
    #%%
    def Play(self): playsound(self.file_name)
    
    #%%
    def SynthScores(self, synth, orde=2):
        synth.ord=self.ord=orde;  # order of score norms
        # deltaNOP    = np.abs(synth.NOP-self.NOP).astype(float)
        deltaSxx    = np.abs(synth.Sxx_dB-self.Sxx_dB)
        deltaMel    = np.abs(synth.FF_coef-self.FF_coef)
        deltaMfccs  = np.abs(synth.mfccs-self.mfccs)
        
        # synth.deltaFmsf     = np.abs(synth.f_msf-self.f_msf)
        # synth.deltaSCI      = np.abs(synth.SCI-self.SCI)
        # synth.deltaEnv      = np.abs(synth.envelope-self.envelope)
        # synth.deltaFF       = 1e-3*np.abs(synth.FF-self.FF)#/np.max(deltaFF)
        # synth.deltaRMS      = np.abs(synth.rms-self.rms)
        # synth.deltaCentroid = 1e-3*np.abs(synth.centroid-self.centroid)
        # synth.deltaF_msf    = 1e-3*np.abs(synth.f_msf-self.f_msf)
        # synth.deltaSxx      = deltaSxx/np.max(deltaSxx)
        # synth.deltaMel      = deltaMel/np.max(deltaMel)
        # synth.deltaMfccs    = deltaMfccs/np.max(deltaMfccs)

        synth.deltaFmsf     = np.abs(synth.f_msf-self.f_msf)/self.f_msf
        synth.deltaSCI      = np.abs(synth.SCI-self.SCI)/self.SCI
        synth.deltaEnv      = np.abs(synth.envelope-self.envelope)/self.envelope
        synth.deltaFF       = np.abs(synth.FF-self.FF)/self.FF
        synth.deltaRMS      = np.abs(synth.rms-self.rms)/self.rms
        synth.deltaCentroid = np.abs(synth.centroid-self.centroid)/self.centroid
        synth.deltaF_msf    = np.abs(synth.f_msf-self.f_msf)/self.f_msf
        synth.deltaSxx      = deltaSxx/np.max(deltaSxx)
        synth.deltaMel      = deltaMel/np.max(deltaMel)
        synth.deltaMfccs    = deltaMfccs/np.max(deltaMfccs)
            
        synth.scoreSCI      = Norm(synth.deltaSCI,      ord=self.ord)/synth.deltaSCI.size
        synth.scoreFF       = Norm(synth.deltaFF,       ord=self.ord)/synth.deltaFF.size
        synth.scoreEnv      = Norm(synth.deltaEnv,      ord=self.ord)/synth.deltaEnv.size
        synth.scoreRMS      = Norm(synth.deltaRMS,      ord=self.ord)/synth.deltaRMS.size
        synth.scoreCentroid = Norm(synth.deltaCentroid, ord=self.ord)/synth.deltaCentroid.size
        synth.scoreF_msf    = Norm(synth.deltaF_msf,    ord=self.ord)/synth.deltaF_msf.size
        synth.scoreSxx      = Norm(synth.deltaSxx,      ord=np.inf)/synth.deltaSxx.size
        synth.scoreMel      = Norm(synth.deltaMel,      ord=np.inf)/synth.deltaSxx.size
        synth.scoreMfccs    = Norm(synth.deltaMfccs,    ord=np.inf)/synth.deltaMfccs.size
        
        # synth.scoreNoHarm        = deltaNOP*10**(deltaNOP-2)
        synth.deltaSCI_mean      = synth.deltaSCI.mean()
        synth.deltaFF_mean       = synth.deltaFF.mean()
        synth.scoreRMS_mean      = synth.scoreRMS.mean()
        synth.scoreCentroid_mean = synth.scoreCentroid.mean()
        synth.deltaEnv_mean      = synth.deltaEnv.mean()
        synth.scoreF_msf_mean    = synth.deltaF_msf.mean()
        
        # -------         acoustic dissimilarity --------------------
        synth.correlation = np.zeros_like(self.time)
        synth.Df          = np.zeros_like(self.time)
        synth.SKL         = np.zeros_like(self.time)
        for i in range(synth.mfccs.shape[1]):
            x, y = self.mfccs[:,i], synth.mfccs[:,i]
            r = Norm(x*y,ord=1)/(Norm(x,ord=2)*Norm(y,ord=2))
            #print(Norm(x*y,ord=1), Norm(x,ord=2), Norm(y,ord=2), r)
            
            synth.correlation[i] = np.sqrt(1-r)
            synth.Df[i]          = 0.5*Norm(x*np.log2(np.abs(x/y))+y*np.log2(np.abs(y/x)), ord=1)
            synth.SKL[i]         = 0.5*Norm(np.abs(x-y), ord=1)
        
            #synth.Df[np.argwhere(np.isnan(synth.Df))]=-10
        
        #synth.correlation /= synth.correlation.max()
        synth.SKL         /= synth.SKL.max()
        synth.Df          /= synth.Df.max()

        synth.scoreCorrelation = Norm(synth.correlation, ord=self.ord)/synth.correlation.size
        synth.scoreSKL         = Norm(synth.SKL, ord=self.ord)/synth.SKL.size
        synth.scoreDF          = Norm(synth.Df, ord=self.ord)/synth.Df.size

        synth.residualCorrelation = synth.scoreFF-np.mean(synth.correlation+synth.Df +synth.scoreSKL)
        synth.SCIFF = synth.scoreSCI + synth.scoreFF

        return synth

    #%%
    def Set(self, p_array):
        p_array = np.array(p_array, dtype=float)
        self.p["a0"].set(value=p_array[0])
        self.p["a1"].set(value=p_array[1])
        self.p["a2"].set(value=p_array[2])
        self.p["b0"].set(value=p_array[3])
        self.p["b1"].set(value=p_array[4])
        self.p["b2"].set(value=p_array[5])
        if len(p_array)>6: 
            self.p["gm"].set(value=p_array[6])

#%%
class Amphibious(Syllable):
    def __init__(self, birdsong=None, t0=0, Nt=100, llambda=1.5, NN=512, overlap=0.5, flim=(1.5e3,2e4), 
                n_mels=4, umbral_FF=1, tlim=[], sfs=[], no_syllable=0, ide="syllable", 
                file_name="syllable", paths=None, f1f2=None, type=""):
        super().__init__(birdsong, t0, Nt, llambda, NN, overlap, flim, 
                         n_mels, umbral_FF, tlim, sfs, no_syllable, ide, 
                         file_name, paths, f1f2, type)
        
        self.p.add_many(('a0', 0.11, False, 0.01, 0.25, None, None),
                        ('a1',   0., False,   -2,    2, None, None),
                        ('a2',   0., False,    0,    2, None, None),
                        ('b0', -0.1, False,   -1,  0.5, None, None),  
                        ('b1',    1, False,    0,    2, None, None), 
                        ('b2',   0., False,    0,    2, None, None), 
                        ('gm',  4e4, False,  1e4,  1e5, None, None))

    #%%
    def MotorGestures(self, alpha, beta, gamma, ovfs=20, prct_noise=0):  # ovfs:oversamp
        t, tmax, dt = 0, int(self.s.size)*ovfs-1, 1./(ovfs*self.fs) # t0, tmax, td
        # pback and pin vectors initialization
        pi, pb, out = np.zeros(tmax), np.zeros(tmax), np.zeros(int(self.s.size))
        # initial vector ODEs (v0), it is not too relevant
        v = 1e-4*np.array([1e2, 1e1, 1]);  self.Vs = [v];
        # ------------- BIRD PARAMETERS -----------
        c, L, r = 3.43E+02, 2.50E-02, 6.50E-01 
        # , Ch, MG, MB, RB, Rh = BirdData['value'] # c, L, r, c, L1, L2, r2, rd 
        # BirdData = pd.read_csv(self.paths.auxdata/'ZonotrichiaData.csv')
        # - Trachea:
        #           r: reflection coeficient    [adimensionelss]
        #           L: trachea length           [m]
        #           c: speed of sound in media  [m/s]
        def ODEs(v):
            dv, [x, y, pout] = np.zeros(3), v  # (x, y, pout)'
            # ----------------- direct implementation of the EDOs -----------
            dv[0] = self.f1(x, y, alpha[t//ovfs], beta[t//ovfs], gamma)
            dv[1] = self.f2(x, y, alpha[t//ovfs], beta[t//ovfs], gamma)
            # ------------------------- trachea ------------------------
            pbold = pb[t]                                 # pressure back before
            # Pin(t) = Ay(t)+pback(t-L/C) = envelope_Signal*v[1]+pb[t-L/C/dt]
            pi[t] = (.5*self.envelope[t//ovfs])*dv[1] + pb[t-int(L/c/dt)] 
            pb[t] = -r*pi[t-int(L/c/dt)]                          # pressure back after: -rPin(t-L/C) 
            pout  = (1-r)*pi[t-int(L/c/dt)]                       # pout
            # ---------------------------------------------------------------
            dv[2] = (pb[t]-pbold)/dt                      # dpout
            return dv        
        # ----------------------- Solving EDOs ----------------------
        while t < tmax: # and v[1] > -5e6:  # labia velocity not too fast
            v = rk4(ODEs, v, dt);  self.Vs.append(v)  # RK4 - step
            out[t//ovfs] = v[-1]               # output signal (synthetic) 
            t += 1;
        # ------------------------------------------------------------
        self.Vs = np.array(self.Vs)
        # define solution (synthetic syllable) as a Syllable object 
        synth = Syllable(Nt=self.Nt, llambda=self.llambda, NN=self.NN, overlap=0.5, flim=self.flim, sfs=[out, self.fs])
        
        synth.id          = self.id+"-synth"
        synth.Vs          = self.Vs
        synth.alpha       = self.alpha
        synth.beta        = self.beta
        synth.timesVs     = np.linspace(0, len(self.s)/self.fs, len(self.s)*ovfs)
        
        delattr(self,"alpha"); delattr(self,"beta");
        
        return synth