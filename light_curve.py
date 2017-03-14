import glob
import os
from io import StringIO

import numpy as np
import pandas as pd
import joblib
from gatspy.periodic import LombScargleFast


class LightCurve():
    def __init__(self, times, measurements, errors, survey=None, name=None,
                 best_period=None, best_score=None, label=None):
        self.times = times
        self.measurements = measurements
        self.errors = errors
        self.survey = survey
        self.name = name
        self.best_period = best_period
        self.best_score = best_score
        self.label = label

    def __repr__(self):
        return "LightCurve(" + ', '.join("{}={}".format(k, v)
                                         for k, v in self.__dict__.items()) + ")"

    def __len__(self):
        return len(self.times)

    def split(self, n_min=0, n_max=np.inf):
        inds = np.arange(len(self.times))
        splits = [x for x in np.array_split(inds, np.arange(n_max, len(inds), step=n_max))
                  if len(x) >= n_min]
        return [LightCurve(survey=self.survey, name=self.name,
                           times=[self.times[i] for i in s],
                           measurements=[self.measurements[i] for i in s],
                           errors=[self.errors[i] for i in s], best_period=self.best_period,
                           best_score=self.best_score, label=self.label)
                for s in splits]

    def fit_lomb_scargle(self):
        period_range = (0.005 * (max(self.times) - min(self.times)),
                        0.95 * (max(self.times) - min(self.times)))
        model_gat = LombScargleFast(fit_period=True, silence_warnings=True,
            optimizer_kwds={'period_range': period_range, 'quiet': True})
        model_gat.fit(self.times, self.measurements, self.errors)
        self.best_period = model_gat.best_period
        self.best_score = model_gat.score(model_gat.best_period).item()

    def load_asas():
        light_curves = []
        bigmacc = pd.read_csv('data/asas/bigmacc.txt', delimiter='\t', index_col='ASAS_ID')
        for fname in glob.glob('./data/asas/*/*'):
            with open(fname) as f:
                dfs = [pd.read_csv(StringIO(chunk), comment='#', delim_whitespace=True) for chunk in f.read().split('#     ')[1:]]
                if len(dfs) > 0:
                    df = pd.concat(dfs)[['HJD', 'MAG_0', 'MER_0', 'GRADE']].sort_values(by='HJD')
                    df = df[df.GRADE <= 'B']
                    df.drop_duplicates(subset=['HJD'], keep='first', inplace=True)
                    lc = LightCurve(name=os.path.basename(fname), survey='ASAS',
                                    times=df.HJD.values, measurements=df.MAG_0.values,
                                    errors=df.MER_0.values)
                    lc.label = bigmacc.loc[lc.name].CLASS if lc.name in bigmacc.index else None
                    lc.fit_lomb_scargle()
                    light_curves.append(lc)
        return light_curves

    def load_linear():
        header_fname = 'data/linear/LINEARattributesFinalApr2013.dat'
        light_curves = []
        header = pd.read_table(header_fname, comment='#', header=None,
                               delim_whitespace=True)
        colnames = [l for l in open(header_fname) if
                    l[0] == '#'][-1].lstrip('#').split()
        header.columns = colnames
        header.set_index('LINEARobjectID', inplace=True)
        LC_types = ['RR_Lyrae_ab', 'RR_Lyrae_c', '???', 'Algol',
                    'Contact_Binary', 'Delta_Scuti']

        for fname in glob.glob('./data/linear/lc/*'):
            df = pd.read_csv(fname, header=0)
            df.drop_duplicates(subset=['mjd'], keep='first', inplace=True)
            lc = LightCurve(name=os.path.splitext(os.path.basename(fname))[0],
                            survey='LINEAR', times=df.mjd.values,
                            measurements=df.m.values, errors=df.merr.values)
            lc.label = LC_types[header.LCtype.loc[int(lc.name)] - 1]
            lc.fit_lomb_scargle()
            light_curves.append(lc)
        return light_curves


if __name__ == "__main__":
    print("Adding light curve data")
#    light_curves = LightCurve.load_asas()
#    joblib.dump(light_curves, 'asas.pkl', compress=3)
    light_curves = LightCurve.load_linear()
    joblib.dump(light_curves, 'linear.pkl', compress=3)