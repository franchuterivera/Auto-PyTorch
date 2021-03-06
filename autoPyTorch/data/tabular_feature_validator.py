import functools
import typing

import numpy as np

import pandas as pd
from pandas.api.types import is_numeric_dtype

import scipy.sparse

import sklearn.utils
from sklearn import preprocessing
from sklearn.base import BaseEstimator
from sklearn.compose import ColumnTransformer
from sklearn.exceptions import NotFittedError

from autoPyTorch.data.base_feature_validator import BaseFeatureValidator, SUPPORTED_FEAT_TYPES


class TabularFeatureValidator(BaseFeatureValidator):
    def _fit(
        self,
        X: SUPPORTED_FEAT_TYPES,
    ) -> BaseEstimator:
        """
        In case input data is a pandas DataFrame, this utility encodes the user provided
        features (from categorical for example) to a numerical value that further stages
        will be able to use

        Arguments:
            X (SUPPORTED_FEAT_TYPES):
                A set of features that are going to be validated (type and dimensionality
                checks) and a encoder fitted in the case the data needs encoding
        Returns:
            self:
                The fitted base estimator
        """

        # The final output of a validator is a numpy array. But pandas
        # gives us information about the column dtype
        if isinstance(X, np.ndarray):
            X = self.numpy_array_to_pandas(X)

        if hasattr(X, "iloc") and not scipy.sparse.issparse(X):
            X = typing.cast(pd.DataFrame, X)
            # Treat a column with all instances a NaN as numerical
            # This will prevent doing encoding to a categorical column made completely
            # out of nan values -- which will trigger a fail, as encoding is not supported
            # with nan values.
            # Columns that are completely made of NaN values are provided to the pipeline
            # so that later stages decide how to handle them
            if np.any(pd.isnull(X)):
                for column in X.columns:
                    if X[column].isna().all():
                        X[column] = pd.to_numeric(X[column])
                        # Also note this change in self.dtypes
                        if len(self.dtypes) != 0:
                            self.dtypes[list(X.columns).index(column)] = X[column].dtype

            if not X.select_dtypes(include='object').empty:
                X = self.infer_objects(X)

            self.enc_columns, self.feat_type = self._get_columns_to_encode(X)

            if len(self.enc_columns) > 0:
                X = self.impute_nan_in_categories(X)

                self.encoder = ColumnTransformer(
                    [
                        ("encoder",
                         preprocessing.OrdinalEncoder(
                             handle_unknown='use_encoded_value',
                             unknown_value=-1,
                         ), self.enc_columns)],
                    remainder="passthrough"
                )

                # Mypy redefinition
                assert self.encoder is not None
                self.encoder.fit(X)

                # The column transformer reoders the feature types - we therefore need to change
                # it as well
                # This means columns are shifted to the right
                def comparator(cmp1: str, cmp2: str) -> int:
                    if (
                        cmp1 == 'categorical' and cmp2 == 'categorical'
                        or cmp1 == 'numerical' and cmp2 == 'numerical'
                    ):
                        return 0
                    elif cmp1 == 'categorical' and cmp2 == 'numerical':
                        return -1
                    elif cmp1 == 'numerical' and cmp2 == 'categorical':
                        return 1
                    else:
                        raise ValueError((cmp1, cmp2))

                self.feat_type = sorted(
                    self.feat_type,
                    key=functools.cmp_to_key(comparator)
                )

                self.categories = [
                    # We fit an ordinal encoder, where all categorical
                    # columns are shifted to the left
                    list(range(len(cat)))
                    for cat in self.encoder.transformers_[0][1].categories_
                ]

            for i, type_ in enumerate(self.feat_type):
                if 'numerical' in type_:
                    self.numerical_columns.append(i)
                else:
                    self.categorical_columns.append(i)

        # Lastly, store the number of features
        self.num_features = np.shape(X)[1]
        return self

    def transform(
        self,
        X: SUPPORTED_FEAT_TYPES,
    ) -> np.ndarray:
        """
        Validates and fit a categorical encoder (if needed) to the features.
        The supported data types are List, numpy arrays and pandas DataFrames.

        Arguments:
            X_train (SUPPORTED_FEAT_TYPES):
                A set of features, whose categorical features are going to be
                transformed

        Return:
            np.ndarray:
                The transformed array
        """
        if not self._is_fitted:
            raise NotFittedError("Cannot call transform on a validator that is not fitted")

        # If a list was provided, it will be converted to pandas
        if isinstance(X, list):
            X, _ = self.list_to_dataframe(X)

        if isinstance(X, np.ndarray):
            X = self.numpy_array_to_pandas(X)

        if hasattr(X, "iloc") and not scipy.sparse.issparse(X):
            if np.any(pd.isnull(X)):
                for column in X.columns:
                    if X[column].isna().all():
                        X[column] = pd.to_numeric(X[column])

            # Also remove the object dtype for new data
            if not X.select_dtypes(include='object').empty:
                X = self.infer_objects(X)

        # Check the data here so we catch problems on new test data
        self._check_data(X)

        # Pandas related transformations
        if hasattr(X, "iloc") and self.encoder is not None:
            if np.any(pd.isnull(X)):
                # After above check it means that if there is a NaN
                # the whole column must be NaN
                # Make sure it is numerical and let the pipeline handle it
                for column in X.columns:
                    if X[column].isna().all():
                        X[column] = pd.to_numeric(X[column])

            # We also need to fillna on the transformation
            # in case test data is provided
            X = self.impute_nan_in_categories(X)

            X = self.encoder.transform(X)

        # Sparse related transformations
        # Not all sparse format support index sorting
        if scipy.sparse.issparse(X) and hasattr(X, 'sort_indices'):
            X.sort_indices()

        try:
            X = sklearn.utils.check_array(
                X,
                force_all_finite=False,
                accept_sparse='csr'
            )
        except Exception as e:
            self.logger.exception(f"Conversion failed for input {X.dtypes} {X}"
                                  "This means AutoPyTorch was not able to properly "
                                  "Extract the dtypes of the provided input features. "
                                  "Please try to manually cast it to a supported "
                                  "numerical or categorical values.")
            raise e
        return X

    def _check_data(
        self,
        X: SUPPORTED_FEAT_TYPES,
    ) -> None:
        """
        Feature dimensionality and data type checks

        Arguments:
            X (SUPPORTED_FEAT_TYPES):
                A set of features that are going to be validated (type and dimensionality
                checks) and a encoder fitted in the case the data needs encoding
        """

        if not isinstance(X, (np.ndarray, pd.DataFrame)) and not scipy.sparse.issparse(X):
            raise ValueError("AutoPyTorch only supports Numpy arrays, Pandas DataFrames,"
                             " scipy sparse and Python Lists, yet, the provided input is"
                             " of type {}".format(type(X))
                             )

        if self.data_type is None:
            self.data_type = type(X)
        if self.data_type != type(X):
            self.logger.warning("AutoPyTorch previously received features of type %s "
                                "yet the current features have type %s. Changing the dtype "
                                "of inputs to an estimator might cause problems" % (
                                    str(self.data_type),
                                    str(type(X)),
                                ),
                                )

        # Do not support category/string numpy data. Only numbers
        if hasattr(X, "dtype"):
            if not np.issubdtype(X.dtype.type, np.number):  # type: ignore[union-attr]
                raise ValueError(
                    "When providing a numpy array to AutoPyTorch, the only valid "
                    "dtypes are numerical ones. The provided data type {} is not supported."
                    "".format(
                        X.dtype.type,  # type: ignore[union-attr]
                    )
                )

        # Then for Pandas, we do not support Nan in categorical columns
        if hasattr(X, "iloc"):
            # If entered here, we have a pandas dataframe
            X = typing.cast(pd.DataFrame, X)

            # Handle objects if possible
            if not X.select_dtypes(include='object').empty:
                X = self.infer_objects(X)

            # Define the column to be encoded here as the feature validator is fitted once
            # per estimator
            enc_columns, _ = self._get_columns_to_encode(X)

            column_order = [column for column in X.columns]
            if len(self.column_order) > 0:
                if self.column_order != column_order:
                    raise ValueError("Changing the column order of the features after fit() is "
                                     "not supported. Fit() method was called with "
                                     "{} whereas the new features have {} as type".format(self.column_order,
                                                                                          column_order,)
                                     )
            else:
                self.column_order = column_order

            dtypes = [dtype.name for dtype in X.dtypes]
            if len(self.dtypes) > 0:
                if self.dtypes != dtypes:
                    raise ValueError("Changing the dtype of the features after fit() is "
                                     "not supported. Fit() method was called with "
                                     "{} whereas the new features have {} as type".format(self.dtypes,
                                                                                          dtypes,
                                                                                          )
                                     )
            else:
                self.dtypes = dtypes

    def _get_columns_to_encode(
        self,
        X: pd.DataFrame,
    ) -> typing.Tuple[typing.List[str], typing.List[str]]:
        """
        Return the columns to be encoded from a pandas dataframe

        Arguments:
            X (pd.DataFrame)
                A set of features that are going to be validated (type and dimensionality
                checks) and a encoder fitted in the case the data needs encoding
        Returns:
            enc_columns (List[str]):
                Columns to encode, if any
            feat_type:
                Type of each column numerical/categorical
        """
        # Register if a column needs encoding
        enc_columns = []

        # Also, register the feature types for the estimator
        feat_type = []

        # Make sure each column is a valid type
        for i, column in enumerate(X.columns):
            if X[column].dtype.name in ['category', 'bool']:

                enc_columns.append(column)
                feat_type.append('categorical')
            # Move away from np.issubdtype as it causes
            # TypeError: data type not understood in certain pandas types
            elif not is_numeric_dtype(X[column]):
                if X[column].dtype.name == 'object':
                    raise ValueError(
                        "Input Column {} has invalid type object. "
                        "Cast it to a valid dtype before using it in AutoPyTorch. "
                        "Valid types are numerical, categorical or boolean. "
                        "You can cast it to a valid dtype using "
                        "pandas.Series.astype ."
                        "If working with string objects, the following "
                        "tutorial illustrates how to work with text data: "
                        "https://scikit-learn.org/stable/tutorial/text_analytics/working_with_text_data.html".format(
                            # noqa: E501
                            column,
                        )
                    )
                elif pd.core.dtypes.common.is_datetime_or_timedelta_dtype(
                    X[column].dtype
                ):
                    raise ValueError(
                        "AutoPyTorch does not support time and/or date datatype as given "
                        "in column {}. Please convert the time information to a numerical value "
                        "first. One example on how to do this can be found on "
                        "https://stats.stackexchange.com/questions/311494/".format(
                            column,
                        )
                    )
                else:
                    raise ValueError(
                        "Input Column {} has unsupported dtype {}. "
                        "Supported column types are categorical/bool/numerical dtypes. "
                        "Make sure your data is formatted in a correct way, "
                        "before feeding it to AutoPyTorch.".format(
                            column,
                            X[column].dtype.name,
                        )
                    )
            else:
                feat_type.append('numerical')
        return enc_columns, feat_type

    def list_to_dataframe(
        self,
        X_train: SUPPORTED_FEAT_TYPES,
        X_test: typing.Optional[SUPPORTED_FEAT_TYPES] = None,
    ) -> typing.Tuple[pd.DataFrame, typing.Optional[pd.DataFrame]]:
        """
        Converts a list to a pandas DataFrame. In this process, column types are inferred.

        If test data is provided, we proactively match it to train data

        Arguments:
            X_train (SUPPORTED_FEAT_TYPES):
                A set of features that are going to be validated (type and dimensionality
                checks) and a encoder fitted in the case the data needs encoding
            X_test (typing.Optional[SUPPORTED_FEAT_TYPES]):
                A hold out set of data used for checking
        Returns:
            pd.DataFrame:
                transformed train data from list to pandas DataFrame
            pd.DataFrame:
                transformed test data from list to pandas DataFrame
        """

        # If a list was provided, it will be converted to pandas
        X_train = pd.DataFrame(data=X_train).infer_objects()
        self.logger.warning("The provided feature types to AutoPyTorch are of type list."
                            "Features have been interpreted as: {}".format([(col, t) for col, t in
                                                                            zip(X_train.columns, X_train.dtypes)]))
        if X_test is not None:
            if not isinstance(X_test, list):
                self.logger.warning("Train features are a list while the provided test data"
                                    "is {}. X_test will be casted as DataFrame.".format(type(X_test))
                                    )
            X_test = pd.DataFrame(data=X_test).infer_objects()
        return X_train, X_test

    def numpy_array_to_pandas(
        self,
        X: np.ndarray,
    ) -> pd.DataFrame:
        """
        Converts a numpy array to pandas for type inference

        Arguments:
            X (np.ndarray):
                data to be interpreted.

        Returns:
            pd.DataFrame
        """
        return pd.DataFrame(X).infer_objects().convert_dtypes()

    def infer_objects(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        In case the input contains object columns, their type is inferred if possible

        This has to be done once, so the test and train data are treated equally

        Arguments:
            X (pd.DataFrame):
                data to be interpreted.

        Returns:
            pd.DataFrame
        """
        if hasattr(self, 'object_dtype_mapping'):
            # Mypy does not process the has attr. This dict is defined below
            for key, dtype in self.object_dtype_mapping.items():  # type: ignore[has-type]
                if 'int' in dtype.name:
                    # In the case train data was interpreted as int
                    # and test data was interpreted as float, because of 0.0
                    # for example, honor training data
                    X[key] = X[key].applymap(np.int64)
                else:
                    try:
                        X[key] = X[key].astype(dtype.name)
                    except Exception as e:
                        # Try inference if possible
                        self.logger.warning(f"Tried to cast column {key} to {dtype} caused {e}")
                        pass
        else:
            X = X.infer_objects()
            for column in X.columns:
                if not is_numeric_dtype(X[column]):
                    X[column] = X[column].astype('category')
            self.object_dtype_mapping = {column: X[column].dtype for column in X.columns}
        self.logger.debug(f"Infer Objects: {self.object_dtype_mapping}")
        return X

    def impute_nan_in_categories(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        impute missing values before encoding,
        remove once sklearn natively supports
        it in ordinal encoding. Sklearn issue:
        "https://github.com/scikit-learn/scikit-learn/issues/17123)"

        Arguments:
            X (pd.DataFrame):
                data to be interpreted.

        Returns:
            pd.DataFrame
        """

        # To be on the safe side, map always to the same missing
        # value per column
        if not hasattr(self, 'dict_nancol_to_missing'):
            self.dict_missing_value_per_col: typing.Dict[str, typing.Any] = {}

        # First make sure that we do not alter the type of the column which cause:
        # TypeError: '<' not supported between instances of 'int' and 'str'
        # in the encoding
        for column in self.enc_columns:
            if X[column].isna().any():
                if column not in self.dict_missing_value_per_col:
                    try:
                        float(X[column].dropna().values[0])
                        can_cast_as_number = True
                    except Exception:
                        can_cast_as_number = False
                    if can_cast_as_number:
                        # In this case, we expect to have a number as category
                        # it might be string, but its value represent a number
                        missing_value: typing.Union[str, int] = '-1' if isinstance(X[column].dropna().values[0],
                                                                                   str) else -1
                    else:
                        missing_value = 'Missing!'

                    # Make sure this missing value is not seen before
                    # Do this check for categorical columns
                    # else modify the value
                    if hasattr(X[column], 'cat'):
                        while missing_value in X[column].cat.categories:
                            if isinstance(missing_value, str):
                                missing_value += '0'
                            else:
                                missing_value += missing_value
                    self.dict_missing_value_per_col[column] = missing_value

                # Convert the frame in place
                X[column].cat.add_categories([self.dict_missing_value_per_col[column]],
                                             inplace=True)
                X.fillna({column: self.dict_missing_value_per_col[column]}, inplace=True)
        return X
