# SST-GNN: Simplified Spatio-temporal Traffic forecasting model using Graph Neural Network

**Authors**
- [Amit Roy](https://amitroy7781.github.io/)
- [Kashob Kumar Roy](https://www.linkedin.com/in/forkkr/) 
- [Amin Ahsan Ali](http://www.cse.iub.edu.bd/faculties/53)
- [M Ashraful Amin](http://www.cse.iub.edu.bd/faculties/25) 
- [A K M Mahbubur Rahman](http://www.cse.iub.edu.bd/faculties/56)

This is the official pytorch implementation of our [paper](https://arxiv.org/abs/2104.00055) SST-GNN: Simplified Spatio-temporal Traffic forecasting model using Graph Neural Network which has been accepted by PAKDD 2021. Check the video presentation of our paper [here](https://youtu.be/Vl4P5IfbuE4)

# Envirnoment Set-Up 

Clone the git project:

```
$ git clone https://github.com/AmitRoy7781/SST-GNN
```

Create a new conda Environment and install required packages (Commands are for ubuntu 16.04)

```
$ conda create -n TrafficEnv python=3.7
$ conda activate TrafficEnv
$ pip install -r requirements.txt
```

# Basic Usage:

**Main Parameters:**

```
--dataset           The input traffic dataset(default:PeMSD7)
--GNN_layers        Number of layers in GNN(default:3)
--num_timestamps    Number of timestamps in Historical and current model(default:12)
--pred_len          Traffic Prediction after how many timestamps(default:3)
--epochs            Number of epochs during training(default:200)
--seed              Random seed. (default: 42)
--cuda              Use GPU if declared
--save_model        Save model if declared
--trained_model     Run pretrained model if declaired
```


**Train Model Using:**
```
$ python3 sst_gnn.py --cuda --dataset PeMSD7 --pred_len 3 --save_model
```

**Run Trained Model:**

Please download the trained SSTGNN models from [Google drive](https://drive.google.com/drive/folders/1xG28Cq3GSG_izfqf37y-__I4CCsc0ONJ?usp=sharing) and place it in `saved_model/PeMSD7` folder

```
$ python3 sst_gnn.py --cuda --dataset PeMSD7  --pred_len 3 --trained_model
```
