''' 
======================================================================================================================
---------------------------------------------------------  TESTING  ---------------------------------------------------
======================================================================================================================
This is my (Honza) script to test and develop in Cobra
import sys
sys.path.append('C:/Local/pers/Documents/GitHub/COBRA/source_code')
'''

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
pd.set_option("display.max_columns",50)

data_path = 'C:/Local/pers/Documents/GitHub/COBRA/datasets/data.csv'
data_types_path = 'C:/Local/pers/Documents/GitHub/COBRA/datasets/data_types.csv'

'''
TO-DO
-sometimes error - no variables with positive coef. Even if error is thrown, return stuff!
-the functions can be applied in a vectorized way
-further improve the forward selection

TEST
'''


'''===================  TEST COBRA INTERFACE ==================='''
import cobra.cobra as c

build = c.COBRA(data_path,
                data_types_path,
                partition_train=0.5,
                partition_select=0.3,
                partition_valid=0.2,
                sampling_1=1,
                sampling_0=1,
                discret_nbins=5,
                regroup_sign=0.001,
                rseed=0)
df_transformed = build.transform()


#I want to try more unisel
df_unisel, df_corr = build.fit_univariate(df_transformed,
                                          preselect_auc=0.53, 
                                          preselect_overtrain=5)

build.plotPredictorQuality(df_unisel)
build.plotCorrMatrix(df_corr)
build.plotIncidence(df_transformed, 'age')

#I want to try more models
#first model
df_model1 = build.fit_model(df_transformed, 
                            df_unisel,
                            modeling_nsteps=30,
                            forced_vars=['scont_1', 'scont_2'],
                            excluded_vars=None,
                            name='All variables')

build.plotAUC(df_model1)
build.plotVariableImportance(df_model1, 5)
build.plotCumulatives([(df_model1,3)], df_transformed)


#second model
df_model2 = build.fit_model(df_transformed, 
                            df_unisel,
                            modeling_nsteps=30,
                            forced_vars=None,
                            excluded_vars=None,
                            name='Experiment')

build.plotAUC(df_model2)
build.plotVariableImportance(df_model2, 6)
build.plotCumulatives([(df_model2, 5)], df_transformed)

#Model comparison
build.plotAUCComparison([(df_model1,3), (df_model2,5)])
build.plotCumulatives([(df_model1,3), (df_model2,5)], df_transformed)
    

def _getTrainSelectValidXY(df):
    '''
    Method split given DF into train/test/validation set in respect to X and Y.
    Returns dictionary with DFs
    ----------------------------------------------------
    df: transformed dataset
    ---------------------------------------------------- 
    '''
    
    dvars = [n for n in df.columns if n[:2] == 'D_']
    
    mask_train = df['PARTITION']=="train"
    mask_selection = df['PARTITION']=="selection"
    mask_validation = df['PARTITION']=="validation"
    
    y_train = df.loc[mask_train,'TARGET']
    y_selection = df.loc[mask_selection,'TARGET']
    y_validation = df.loc[mask_validation,'TARGET']
    
    x_train = df.loc[mask_train,dvars]
    x_selection = df.loc[mask_selection,dvars]
    x_validation = df.loc[mask_validation,dvars]
    
    dict_out = {'y_train':y_train, 'y_selection':y_selection, 'y_validation':y_validation, 
                'x_train':x_train, 'x_selection':x_selection, 'x_validation':x_validation}
    
    return dict_out

_partition_dict = _getTrainSelectValidXY(df_transformed)

''' 
=============================================================================================================
=============================================================================================================
=============================================================================================================
-Only boolean target
'''
from sklearn.linear_model import LogisticRegression
from sklearn import metrics
import numpy as np

df_sel = df_unisel
forced_vars = ['scont_1', 'scont_2']
excluded_vars = None
positive_only = True

#if None, replace by empty list
if not excluded_vars:
    excluded_vars = []
    
if not forced_vars:
    forced_vars = []

#Sort
df_sel = df_sel.sort_values(by='AUC selection', ascending=False)

#Build list of variables to be used for Forward selection
preselected_vars = df_sel['variable'][df_sel['preselection'] == True].tolist()
preselected_vars = [var for var in preselected_vars if var not in forced_vars+excluded_vars]
all_vars = ['D_' + var for var in forced_vars + preselected_vars]



''' 
------------------  MAIN LOOP  ------------------
'''
df_forward_selection = pd.DataFrame(None,columns=[
                                                  'step',
                                                  'coef',
                                                  'all_coefs_positive',
                                                  'AUC_train',
                                                  'AUC_selection',
                                                  'AUC_validation',
                                                  'predictors_subset',
                                                  'last_var_added',
                                                  'AUC_train_rank',
                                                  'selected_model',
                                                  'pred_training',
                                                  'pred_selection',
                                                  'pred_validation'
                                                  ])
        
f_position_forced = lambda i, forced, all_vars: len(forced) if i <= len(forced) else len(all_vars)

n_steps = min(30,len(all_vars))
predictors = []
row = 0

for step in range(1,n_steps):
    print('*******************Iter {}*******************'.format(step))
    
    pos = f_position_forced(step, forced_vars, all_vars)
    remaining_predictors = [var for var in all_vars[:pos] if var not in predictors]
    
    for predictor in remaining_predictors:
        predictors_subset = predictors + [predictor]
        #Train - train model
        logit = LogisticRegression(fit_intercept=True, C=1e9, solver = 'liblinear')
        logit.fit(y=_partition_dict['y_train'], X=_partition_dict['x_train'][predictors_subset])
        
        #Train - predict and AUC
        y_pred_train = logit.predict_proba(_partition_dict['x_train'][predictors_subset])
        AUC_train = metrics.roc_auc_score(y_true=_partition_dict['y_train'], y_score=y_pred_train[:,1])
        
        #Selection - predict and AUC
        y_pred_selection = logit.predict_proba(_partition_dict['x_selection'][predictors_subset])
        AUC_selection = metrics.roc_auc_score(y_true=_partition_dict['y_selection'], y_score=y_pred_selection[:,1])
        
        #Validation - predict and AUC
        y_pred_validation = logit.predict_proba(_partition_dict['x_validation'][predictors_subset])
        AUC_validation = metrics.roc_auc_score(y_true=_partition_dict['y_validation'], y_score=y_pred_validation[:,1])
        
        #check if coefs are positive
        all_coefs_positive = (logit.coef_[0] >= 0).all()
        
        df_forward_selection.loc[row] = [
                                         step,
                                         logit.coef_,
                                         all_coefs_positive,
                                         AUC_train,
                                         AUC_selection,
                                         AUC_validation,
                                         predictors_subset,
                                         predictors_subset[-1],
                                         0,
                                         False,
                                         y_pred_train,
                                         y_pred_selection,
                                         y_pred_validation
                                         ]
        row +=1
        
    #Only positive coefs
    if positive_only:
        if len(df_forward_selection[(df_forward_selection['all_coefs_positive'] == True) & (df_forward_selection['step'] == step)]) == 0:
            raise ValueError("No models with only positive coefficients","NormalStop")
        
        ##Find best model
        #Sort AUC by size
        df_forward_selection['AUC_train_rank'] = df_forward_selection.groupby('step')['AUC_train'].rank(ascending=False)
        
        #Find model where AUC is highest AND all coefs are positive - convert to boolean flag
        df_forward_selection['selected_model'] = df_forward_selection[df_forward_selection['all_coefs_positive'] == True].groupby(['step'])['AUC_train'].transform(max)
        df_forward_selection['selected_model'] = (df_forward_selection['selected_model'] == df_forward_selection['AUC_train'])
    else:
        ##Highest AUC, regardless of coefs
        df_forward_selection['selected_model'] = (df_forward_selection.groupby(['step'])['AUC_train'].transform(max) == df_forward_selection['AUC_train'])
        
    ##Add next predictor
    add_variable = df_forward_selection.loc[(df_forward_selection['selected_model'] == True) & (df_forward_selection['step'] == step), 'last_var_added'].iloc[0]
    predictors.append(add_variable)
    
    clmns_out = ['step', 'coef', 'AUC_train', 'AUC_selection', 'AUC_validation', 'predictors_subset', 'last_var_added',
                 'pred_training','pred_selection','pred_validation']

df_tst = df_forward_selection[clmns_out][df_forward_selection['selected_model'] == True]

''' 
=============================================================================================================
============================================ IMPORTANCE ==================================================
=============================================================================================================
-Only boolean target
'''
def __eqfreq(var, train, autobins=True, nbins=10, precision=0, twobins=True, catchLarge=True):
    '''
    Special method for binning continuous variables into bins
    ----------------------------------------------------
    var: input pd.Serie with continuous columns
    train: mask with rows which belongs to train
    autobins: adapts number of bins
    nbins: number of bins
    precision: precision to form meaningful bins
    twobins: if only two bins are found, iterate to find more
    catchLarge: check when groups are too big
    ---------------------------------------------------- 
    - This function is a reworked version of pd.qcut to satisfy our particular needs
    - Takes for var a continuous pd.Series as input and returns a pd.Series with bin-labels (e.g. [4,6[ )
    - Train takes a series/list of booleans (note: we define bins based on the training set)
    - Autobins reduces the number of bins (starting from nbins) as a function of the number of missings
    - Nbins is the wished number of bins
    - Precision=0 results in integer bin-labels if possible
    - twobins=True forces the function to output at least two bins
    - catchLarge tests if some groups (or missing group) are very large, and if so catches and outputs two groups
    - note: catchLarge makes twobins irrelevant
    '''

    # Test for large groups and if one exists pass them with two bins: Large_group,Other
    if catchLarge:
        catchPercentage=1-(1/nbins)
        groupCount = var[train].groupby(by=var[train]).count()
        maxGroupPerc = groupCount.max()/len(var[train])
        missingPerc = sum(var[train].isnull())/len(var[train])
        if maxGroupPerc>=catchPercentage:
            largeGroup = groupCount.sort_values(ascending=False).index[0]
            x_binned = var.copy()
            x_binned.name = 'B_'+var.name
            x_binned[x_binned!=largeGroup]='Other'
            cutpoints=None
            info = (var.name+": One large group, outputting 2 groups")
            return x_binned, cutpoints, info
        elif missingPerc>=catchPercentage:
            x_binned = var.copy()
            x_binned.name = 'B_'+var.name
            x_binned[x_binned.isnull()]='Missing'
            x_binned[x_binned!='Missing']='Other'
            cutpoints=None
            info = (var.name+": One large missing group, outputting 2 groups")
            return x_binned, cutpoints, info
    # Adapt number of bins as a function of number of missings
    if autobins:
        length = len(var[train])
        missing_total = var[train].isnull().sum()
        missing_perten = missing_total/length*10
        nbins = max(round(10-missing_perten)*nbins/10 ,1)
    # Store the name and index of the variable
    name = var.name
    series_index = var.index
    # Transform var and train to a np.array and list respectively, which is needed for some particular function&methods
    x = np.asarray(var)
    train = list(train)
    # First step in finding the bins is determining what the quantiles are (named as cutpoints)
    # If the quantile lies between 2 points we use lin interpolation to determine it
    cutpoints = var[train].quantile(np.linspace(0,1,nbins+1),interpolation = 'linear')
    # If the variable results only in 2 unique quantiles (due to skewness) increase number of quantiles until more than 2 bins can be formed
    if twobins:
        extrasteps = 1
        # Include a max. extrasteps to avoid infinite loop
        while (len(cutpoints.unique())<=2) & (extrasteps<20):
            cutpoints = var[train].quantile(np.linspace(0,1,nbins+1+extrasteps),interpolation = 'linear')
            extrasteps+=1
    # We store which rows of the variable x lies under/above the lowest/highest cutpoint 
    # Without np.errstate(): x<cutpoints.min() or x>cutpoints.max() can give <RuntimeWarning> if x contains nan values (missings)
    # However the function will result in False in both >&< cases, which is a correct result, so the warning can be ignored
    with np.errstate(invalid='ignore'):
        under_lowestbin = x < cutpoints.min()
        above_highestbin= x > cutpoints.max()


    def _binnedx_from_cutpoints(x, cutpoints, precision, under_lowestbin, above_highestbin):
    ### Attributes the correct bin ........................
    ### Function that, based on the cutpoints, seeks the lowest precision necessary to have meaningful bins
    ###  e.g. (5.5,5.5] ==> (5.51,5.54]
    ### Attributes those bins to each value of x, to achieve a binned version of x   
        
        # Store unique cutpoints (e.g. from 1,3,3,5 to 1,3,5) to avoid inconsistensies when bin-label making
        # Indeed, bins [...,1], (1,3], (3,3], (3,5], (5,...] do not make much sense
        # While, bins  [...,1], (1,3],        (3,5], (5,...] do make sense
        unique_cutpoints = cutpoints.unique()
        # If there are only 2 unique cutpoints (and thus only one bin will be returned), 
        # keep original values and code missings as 'Missing'
        if len(unique_cutpoints) <= 2:
            cutpoints = None
            x_binned = pd.Series(x)
            x_binned[x_binned.isnull()] = 'Missing'
            info = (var.name+": Only one resulting bin, keeping original values instead")
            return x_binned, cutpoints, info
        # Store info on whether or not the number of resulting bins equals the desired number of bins
        elif len(unique_cutpoints) < len(cutpoints):
            info = (var.name+": Resulting # bins < whished # bins")
        else:
            info = (var.name+": Resulting # bins as desired")
        # Finally, recode the cutpoints (which can have doubles) as the unique cutpoints
        cutpoints = unique_cutpoints
        
        # Store missing values in the variable as a mask, and create a flag to test if there are any missing in the variable
        na_mask = np.isnan(x)
        has_nas = na_mask.any()
        # Attribute to every x-value the index of the cutpoint (from the sorted cutpoint list) which is equal or higher than
        # the x-value, effectively encompasing that x-value.
        # e.g. for x=6 and for sorted_cutpoint_list=[0,3,5,8,...] the resulting_index=3    
        ids = cutpoints.searchsorted(x, side='left')
        # x-values equal to the lowest cutpoint will recieve a ids value of 0
        # but our code to attribute bins to x-values based on ids (see end of this subfunction) requires a min. value of 1
        ids[x == cutpoints[0]] = 1
        # Idem as previous: x-values below the lowest cutpoint should recieve a min. value of 1
        if under_lowestbin.any():
            ids[under_lowestbin] = 1
        # Similar as previous: x-values above the highest cutpoint should recieve the max. allowed ids
        if above_highestbin.any():
            max_ids_allowed = ids[(above_highestbin == False) & (na_mask==False)].max()
            ids[above_highestbin] = max_ids_allowed
        # Maximal ids can now be defined if we neglect ids of missing values
        max_ids = ids[na_mask==False].max()
        
        # Based on the cutpoints create bin-labels
        # Iteratively go through each precision (= number of decimals) until meaningful bins are formed
        # If theoretical bin is ]5.51689,5.83654] we will prefer ]5.5,5.8] as output bin
        increases = 0
        original_precision = precision
        while True:
            try:
                bins = _format_bins(cutpoints, precision)
            except ValueError:
                increases += 1
                precision += 1
                #if increases >= 5:
                    #warnings.warn("Modifying precision from "+str(original_precision)+" to "+str(precision)+" to achieve discretization")
                    #print("Modifying precision from "+str(original_precision)+" to "+str(precision)+" to achieve discretization")
            else:
                break
        
        # Make array of bins to allow vector-like attribution
        bins = np.asarray(bins, dtype=object)
        # If x has nas: for each na-value, set the ids-value to max_ids+1
        # this will allow na-values to be attributed the highest bin which we define right below
        if has_nas:
            np.putmask(ids, na_mask, max_ids+1)
        # The highest bin is defined as 'Missing'
        bins = np.append(bins,'Missing')
        # ids-1 is used as index in the bin-labels list to attribute a bin-label to each x. Example:
        # x=6   sorted_cutpoint_list=[0,3,5,8,...]   ids=3   levels=[[0,3],(3,5],(5,8],...]
        # The correct bin level for x is (5,8] which has index 2 which is equal to the ids-1
        x_binned = bins[ids-1]
        return x_binned, cutpoints, info
        

    def _format_bins(cutpoints, prec):
    # Based on the quantile list create bins. Raise error if values are similar within one bin.
    # On error _binnedx_from_cutpoints will increase precision
        
        fmt = lambda v: _format_label(v, precision=prec)
        bins = []
        for a, b in zip(cutpoints, cutpoints[1:]):
            fa, fb = fmt(a), fmt(b)
            
            if a != b and fa == fb:
                raise ValueError('precision too low')
                
            formatted = '(%s, %s]' % (fa, fb)
            bins.append(formatted)
        
        bins[0] = '[...,' + bins[0].split(",")[-1]
        bins[-1] = bins[-1].split(",")[0] + ',...]'
        return bins


    def _format_label(x, precision):
    # For a specific precision, returns the value formatted with the appropriate amount of numbers after comma and correct brackets
    
        if isinstance(x,float):
            frac, whole = np.modf(x)
            sgn = '-' if x < 0 else ''
            whole = abs(whole)
            if frac != 0.0:
                val = '{0:.{1}f}'.format(frac, precision)
                val = _trim_zeros(val)
                if '.' in val:
                    return sgn + '.'.join(('%d' % whole, val.split('.')[1]))
                else: 
                    if '0' in val:
                        return sgn + '%0.f' % whole
                    else:
                        return sgn + '%0.f' % (whole+1)
            else:
                return sgn + '%0.f' % whole
        else:
            return str(x)


    def _trim_zeros(x):
    # Removes unnecessary zeros and commas
        while len(x) > 1 and x[-1] == '0':
            x = x[:-1]
        if len(x) > 1 and x[-1] == '.':
            x = x[:-1]
        return x
    
    x_binned, cutpoints, info = _binnedx_from_cutpoints(x, cutpoints, precision=precision, under_lowestbin=under_lowestbin, above_highestbin=above_highestbin)
    x_binned = pd.Series(x_binned, index=series_index, name="B_"+name)
    return x_binned, cutpoints, info

def __increp(b_var, target, train):    
    '''
    Method for incidence replacement
    Returns replaced pd.Serie
    ----------------------------------------------------
    b_var: input pd.Serie to be replaced
    target: pd.Serie with target variable
    train: pd.Serie with parition variable
    ---------------------------------------------------- 
    '''
    
    #get variable name
    name = b_var.name
    #get overall incidence 
    incidence_mean = target[train].mean()
    #get incidence per group
    incidences = target[train].groupby(b_var).mean()
    #construct dataframe with incidences
    idf = pd.DataFrame(incidences).reset_index()
    #get values that are in the data but not in the labels
    bin_labels = incidences.index
    newgroups = list(set(b_var.unique()) ^ set(bin_labels))
    #if newgroups, add mean incidence to incidence dataframe for each new group
    if len(newgroups)>0:
        #make dataframe:
        ngdf = pd.DataFrame(newgroups)
        ngdf.columns = [name]
        ngdf["TARGET"] = incidence_mean
        #dataframe with incidences:    
        idf = idf.append(ngdf)
    #dataframe with the variable
    vdf = pd.DataFrame(b_var)
    #discretized variable by merge
    d_var = pd.merge(vdf,idf,how='left',on=name)["TARGET"]
    return pd.Series(d_var, name="D_"+name[2:])




#
# LOAD CSV
#
df = pd.read_csv(data_path, header=0, sep=None, engine='python')


#
# PREPARE DATA
#
clmn = 'scont_1'
df_prep = df[['TARGET',clmn]]

#
# ADD PARTITION
#
import math

np.random.seed(0)

_partitioning_settings = {'train':0.5,
                          'selection':0.3, 
                          'validation':0.2}


#
# BINNING
#

for i in range(1,41):
    
    #PARTITION
    df_prep = df_prep.iloc[np.random.permutation(len(df_prep))].sort_values(by='TARGET', ascending=False).reset_index(drop=True)
    partition = []
    sorted_target=df_prep['TARGET'] #Just the target since it is allready sorted (see above)
    for target in [sorted_target.iloc[0],sorted_target.iloc[-1]]:
        target_length = (sorted_target==target).sum()
        
        for part, size in _partitioning_settings.items():
            partition.extend([part]*math.ceil(target_length*size))
            
    df_prep["PARTITION"] = partition[:len(df_prep)]
    
    #Binns
    result = __eqfreq(var=df_prep[clmn],
                      train=df_prep["PARTITION"]=="train",
                      autobins=True,
                      	nbins=5,
                      precision=0,
                      twobins=True,
                      # TRUE OPTION STILL PRODUCES ERROR IN SORTNUMERIC function AND SCORING procedure !!!!!!!!!
                     catchLarge=False)
    
    bin_serie = pd.Series(result[0])
    
    #REPLACE INCIDENCE
    inc_rep = __increp(b_var=bin_serie,
                       target=df_prep['TARGET'],
                       train=df_prep['PARTITION']=="train") 
    
    df_prep['D_'+clmn] = inc_rep
   
    #PREDICT
    y_train = df_prep['TARGET'][df_prep['PARTITION'] == 'train'].as_matrix()
    x_train = df_prep['D_'+clmn][df_prep['PARTITION'] == 'train'].as_matrix()
    
    logit = LogisticRegression(fit_intercept=True, C=1e9, solver = 'liblinear')
    logit.fit(y=y_train, X=x_train.reshape(-1,1))
    
    coefs = logit.coef_[0]
    
    print('ITERATION {}, lenght: {}, coef: {}'.format(i, len(np.unique(result[0])),coefs))
    
































res = pd.Series(result[0]) 
res.groupby(res).count()














#
#
#
df_transformed.groupby('D_scont_1')['D_scont_1'].count()
df_transformed.groupby('B_scont_1')['B_scont_1'].count()


















