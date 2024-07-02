# QPy description

This library is an interface to the terrestrial biosphere model [QUINCY](https://www.bgc-jena.mpg.de/en/bsi/projects/quincy). 
It contains:
1. **QNetCDF**: A library to parse QUINCY NetCDF output (unsorted)
2. **QPy-Manip**: A library for seamless manipulation of QUINCY settings (namelist and lctlib files)
3. **Quincy-Pyui**: A graphical users interface that allows conducting QUINCY simulation experiments on your local machine


# Setup 

## Prerequisites
QPy requires the following installed libraries to be used:
1. python installed via anaconda or miniconda (pip also works but not tested)
CMake
3. cpp compiler
4. fortran compiler
5. cmake
6. quincy branch from [DKRZ](https://gitlab.dkrz.de/quincy-community/quincy-model-developers/qs-development/-/tree/feature/cmake-build):

### Mac-os
The easiest way to install anaconda on Mac is using [homebrew](https://brew.sh/)

`brew install --cask anaconda`

Both cpp and fortran compilers can be installed using the GNU
compiler suite also available via homebrew:

`brew install gcc`

Finally, cmake is also availble via homebrew:

`brew install cmake`

### Linux (ubuntu)

You guys typically know how to do it ;) 
Anaconda can be installed following this [link](https://phoenixnap.com/kb/install-anaconda-ubuntu).
A gcc version (including a cpp and a fotran compiler) should be part of the build essnetials:

`sudo apt install build-essential`

Finally cmake can be installed using the following commands
`sudo apt-get install libssl-dev`


### Windows

For windows multiple cpp and fortran compilers exist. For simplicity, we recommend installing gcc installed via scoop.
Therefore, we open a PowerShell terminal and run:
```
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
Invoke-RestMethod -Uri https://get.scoop.sh | Invoke-Expression
```

We install all required libraries but anaconda using scoop:
```
 scoop install git
 scoop bucket add main
 scoop install main/make
 scoop install main/mingw
 scoop install main/gcc
 scoop install main/cmake
```
**Note**: The order of commands is strictly mandatory. For now mingw cpp compiler do not work under Windows 10, but 
the gcc library does work. Furthermore, we need mingw as ot offers a fortran compiler.

Anaconda can be obtained from the web folling this [link]( https://repo.anaconda.com/archive/Anaconda3-2024.06-1-Windows-x86_64.exe).




## Installation

### Mac-os and Linux

#### python environment
After installation of anaconda a new python environment
*QPy* should be created and all required python libraries 
should be installed. We can do that via the following commands:

```
conda create --name QPy python=3.9
conda activate QPy

conda install -y matplotlib
conda install -y conda-forge::cartopy
conda install -y -c conda-forge xarray netCDF4 
conda install -y -c conda-forge pybind11
conda install -y numpy
conda install -y pandas
conda install -y conda-forge::pyqt
conda install -y scipy
conda install -y pyopengl
```
Note: For now pyopengl is optional and not required for the user interface.

### Windows
We start the **anaconda powershell** and run the following conda commands:
```
conda create --name QPy python=3.9
conda activate QPy
conda install -y pandas
pip install netcdf4
pip install xarray
pip install cartopy
pip install pyqt5-tools
```

**Note**: This mismatch in installation step compared to the linux/mac builds is caused by the downloaded anaconda binary already containing
PyQT5 libraries which have to be *carefully* extended with the other needed libaries and a full conda based
instlallation causes trouble. 
## Configuration

## 1 QNetCDF
This deserves more description, I know... 
Does not require any additional compilers other than the previously installed *QPy* conda environment.
It can however be sped up if a cpp compiler is available. 

## 2 QPy-Manip
This does not require any additional compilers and libraries other than the *QPy* conda environment.
## 3 Quincy-Pyui

After creating clone this repository and creating the *QPy* conda environment one has to navigate to
`app` directory via the terminal. In this directory we execute
`python run_model_user_interface.py` 


