#!/bin/zsh

# Set the environment name
ENV_NAME=qBittorrent

# Check if conda is installed
if ! command -v conda &> /dev/null
then
  echo "Conda is not installed. Please install conda."
  exit 1
fi

# Check if environment already exists
if conda env list | grep -q "$ENV_NAME"
then
  echo "Environment $ENV_NAME already exists. Skipping creation."
else
  echo "Creating environment $ENV_NAME..."
  conda env create -f environment.yml
  if [ $? -ne 0 ]; then
    echo "Failed to create environment $ENV_NAME. Check the environment.yml file."
    exit 1
  fi
  echo "Environment $ENV_NAME created successfully."
fi

# Activate the environment
echo "Activating environment $ENV_NAME..."
eval "$(conda shell.bash hook)"
conda activate $ENV_NAME

# Verify the installation
echo "Verifying dependencies..."
python -m pip check

echo "Environment $ENV_NAME is ready to use."