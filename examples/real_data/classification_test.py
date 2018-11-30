__author__ = "Max Dippel, Michael Burkart and Matthias Urban"
__version__ = "0.0.1"
__license__ = "BSD"


import os, sys
sys.path.append(os.path.abspath(os.path.join(__file__, "..", "..", "..")))
import logging

from autoPyTorch import AutoNetClassification

from autoPyTorch.data_management.data_manager import DataManager

dm = DataManager(verbose=1)
dataset_dir = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..', '..', 'datasets'))

# choose between the 10 classification testcases on real data.
TEST_CASE = 4

if TEST_CASE == 1:
    dm.read_data(os.path.join(dataset_dir, "classification/dataset_22_mfeat-zernike.csv"), is_classification=True)
    # 2000 samples, 10 classes, 48 features

if TEST_CASE == 2:
    dm.read_data(os.path.join(dataset_dir, "classification/phpbL6t4U.csv"), is_classification=True)
    # 13910 samples, 6 classes, 128 features

if TEST_CASE == 3:
    dm.read_data(os.path.join(dataset_dir, "classification/php0iVrYT.csv"), is_classification=True)
    # 748 samples, 2 classes, 4 features
    
if TEST_CASE == 4:
    dm.read_data(os.path.join(dataset_dir, "classification/dataset_31_credit-g.csv"), is_classification=True)

if TEST_CASE == 5:
    dm.read_data(os.path.join(dataset_dir, "classification/dataset_28_optdigits.csv"), is_classification=True)
    # 5620 samples, 10 classes, 65 features

if TEST_CASE == 6:
    dm.read_data(os.path.join(dataset_dir, "classification/dataset_42_soybean.csv"), is_classification=True)
    # 683 samples, 19 classes, 36 categorical features

if TEST_CASE == 7:
    dm.read_data(os.path.join(dataset_dir, "classification/dataset_44_spambase.csv"), is_classification=True)
    # 4601 samples, 2 classes, 58 features
    
if TEST_CASE == 8:
    dm.read_data(os.path.join(dataset_dir, "classification/dataset_32_pendigits.csv"), is_classification=True)
    
if TEST_CASE == 9:
    dm.read_data(os.path.join(dataset_dir, "classification/php4fATLZ.csv"), is_classification=True)

if TEST_CASE == 10:
    dm.read_data(os.path.join(dataset_dir, "classification/phpnBqZGZ.csv"), is_classification=True)


autonet = AutoNetClassification(budget_type='epochs', min_budget=1, max_budget=9, num_iterations=1, log_level='info')

res = autonet.fit(X_train=dm.X_train,
                  Y_train=dm.Y_train,
                  early_stopping_patience=3,
                  # validation_split=0.3,
                  categorical_features=dm.categorical_features)

print(res)
