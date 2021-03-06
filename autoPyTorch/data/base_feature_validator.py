import logging
import typing

import numpy as np

import pandas as pd

import scipy.sparse

from sklearn.base import BaseEstimator

from autoPyTorch.utils.logging_ import PicklableClientLogger


SUPPORTED_FEAT_TYPES = typing.Union[
    typing.List,
    pd.DataFrame,
    np.ndarray,
    scipy.sparse.bsr_matrix,
    scipy.sparse.coo_matrix,
    scipy.sparse.csc_matrix,
    scipy.sparse.csr_matrix,
    scipy.sparse.dia_matrix,
    scipy.sparse.dok_matrix,
    scipy.sparse.lil_matrix,
]


class BaseFeatureValidator(BaseEstimator):
    """
    A class to pre-process features. In this regards, the format of the data is checked,
    and if applicable, features are encoded
    Attributes:
        feat_type (List[str]):
            List of the column types found by this estimator during fit.
        data_type (str):
            Class name of the data type provided during fit.
        encoder (typing.Optional[BaseEstimator])
            Host a encoder object if the data requires transformation (for example,
            if provided a categorical column in a pandas DataFrame)
        enc_columns (typing.List[str])
            List of columns that were encoded.
    """
    def __init__(self,
                 logger: typing.Optional[typing.Union[PicklableClientLogger, logging.Logger
                                                      ]] = None,
                 ) -> None:
        # Register types to detect unsupported data format changes
        self.feat_type = None  # type: typing.Optional[typing.List[str]]
        self.data_type = None  # type: typing.Optional[type]
        self.dtypes = []  # type: typing.List[str]
        self.column_order = []  # type: typing.List[str]

        self.encoder = None  # type: typing.Optional[BaseEstimator]
        self.enc_columns = []  # type: typing.List[str]

        self.logger: typing.Union[
            PicklableClientLogger, logging.Logger
        ] = logger if logger is not None else logging.getLogger(__name__)

        # Required for dataset properties
        self.num_features = None  # type: typing.Optional[int]
        self.categories = []  # type: typing.List[typing.List[int]]
        self.categorical_columns: typing.List[int] = []
        self.numerical_columns: typing.List[int] = []

        self._is_fitted = False

    def fit(
        self,
        X_train: SUPPORTED_FEAT_TYPES,
        X_test: typing.Optional[SUPPORTED_FEAT_TYPES] = None,
    ) -> BaseEstimator:
        """
        Validates and fit a categorical encoder (if needed) to the features.
        The supported data types are List, numpy arrays and pandas DataFrames.
        CSR sparse data types are also supported

        Arguments:
            X_train (SUPPORTED_FEAT_TYPES):
                A set of features that are going to be validated (type and dimensionality
                checks) and a encoder fitted in the case the data needs encoding
            X_test (typing.Optional[SUPPORTED_FEAT_TYPES]):
                A hold out set of data used for checking
        """

        # If a list was provided, it will be converted to pandas
        if isinstance(X_train, list):
            X_train, X_test = self.list_to_dataframe(X_train, X_test)

        self._check_data(X_train)

        if X_test is not None:
            self._check_data(X_test)

            if np.shape(X_train)[1] != np.shape(X_test)[1]:
                raise ValueError("The feature dimensionality of the train and test "
                                 "data does not match train({}) != test({})".format(
                                     np.shape(X_train)[1],
                                     np.shape(X_test)[1]
                                 ))

        # Fit on the training data
        self._fit(X_train)

        self._is_fitted = True

        return self

    def _fit(
        self,
        X: SUPPORTED_FEAT_TYPES,
    ) -> BaseEstimator:
        """
        Arguments:
            X (SUPPORTED_FEAT_TYPES):
                A set of features that are going to be validated (type and dimensionality
                checks) and a encoder fitted in the case the data needs encoding
        Returns:
            self:
                The fitted base estimator
        """
        raise NotImplementedError()

    def transform(
        self,
        X: SUPPORTED_FEAT_TYPES,
    ) -> np.ndarray:
        """
        Arguments:
            X_train (SUPPORTED_FEAT_TYPES):
                A set of features, whose categorical features are going to be
                transformed

        Return:
            np.ndarray:
                The transformed array
        """
        raise NotImplementedError()
