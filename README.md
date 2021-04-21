# Auto-PyTorch

Copyright (C) 2019  [AutoML Group Freiburg](http://www.automl.org/)

This an alpha version of Auto-PyTorch with improved API.
So far, Auto-PyTorch supports tabular data (classification, regression).
We plan to enable image data and time-series data.


Find the documentation [here](https://automl.github.io/Auto-PyTorch/refactor_development)


## Installation

### Manual Installation

We recommend using Anaconda for developing as follows:

```sh
# Following commands assume the user is in a cloned directory of Auto-Pytorch

# We also need to initialize the automl_common repository as follows
# You can find more information about this here:
# https://github.com/automl/automl_common/
git submodule update --init --recursive

# Create the environment
conda create -n autopytorch python=3.8
conda activate autopytorch
conda install gxx_linux-64 gcc_linux-64 swig
cat requirements.txt | xargs -n 1 -L 1 pip install
python setup.py install

```

### Pip
TODO

## Contributing

If you want to contribute to Auto-PyTorch, clone the repository and checkout our current development branch

```sh
$ git checkout refactor_development
```


## Examples

For a detailed tutorial, please refer to the jupyter notebook in https://github.com/automl/Auto-PyTorch/tree/master/examples/basics.

In a nutshell:

```py
from autoPyTorch import TODO
```

For ore examples, checkout `examples/`.


## Configuration

### Pipeline configuration

### Search space

### Fitting single configurations


## License

This program is free software: you can redistribute it and/or modify
it under the terms of the Apache license 2.0 (please see the LICENSE file).

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

You should have received a copy of the Apache license 2.0
along with this program (see LICENSE file).

## Reference

```
@incollection{mendoza-automlbook18a,
  author    = {Hector Mendoza and Aaron Klein and Matthias Feurer and Jost Tobias Springenberg and Matthias Urban and Michael Burkart and Max Dippel and Marius Lindauer and Frank Hutter},
  title     = {Towards Automatically-Tuned Deep Neural Networks},
  year      = {2018},
  month     = dec,
  editor    = {Hutter, Frank and Kotthoff, Lars and Vanschoren, Joaquin},
  booktitle = {AutoML: Methods, Sytems, Challenges},
  publisher = {Springer},
  chapter   = {7},
  pages     = {141--156},
  note      = {To appear.},
}
```

**Note**: Previously, the name of the project was AutoNet. Since this was too generic, we changed the name to AutoPyTorch. AutoNet 2.0 in the reference mention above is indeed AutoPyTorch.


## Contact

Auto-PyTorch is developed by the [AutoML Group of the University of Freiburg](http://www.automl.org/).
