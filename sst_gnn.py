
#Model: SST-GNN Model

# Packages

import sys
import os
import torch
import argparse
import pyhocon
import random
import math
import copy
from sklearn.utils import shuffle
from sklearn.metrics import f1_score
from sklearn.metrics import r2_score
from sklearn.metrics import mean_absolute_error
import torch.nn as nn
import numpy as np
import torch.nn.functional as F
import time
from collections import defaultdict
import matplotlib.pyplot as plt
import pandas as pd
import pickle
from datetime import datetime

# Data Center

class DataCenter(object):

    def __init__(self, config):
        super(DataCenter, self).__init__()
        self.config = config

    def getPositionEmbedding(self,pos):
      input = np.arange(0,pos+1,1)
      a = input * 360
      day = a / 288
      week = a / 2016
      month = a / 8640
      day = np.deg2rad(day)
      week = np.deg2rad(week)
      day = np.sin(day)
      week = np.sin(week)
      combined = day+week
      return combined

  

    def load_data(self,ds,st_day,en_day,hr_sample,day,pred_len):

        content_file = self.config['file_path.' + ds + '_content']

        if ds=="PeMSD8" or ds == "PeMSD4":
          timestamp_data = np.load(content_file)
          timestamp_data = timestamp_data[:,:,2]
        else:
          timestamp_data = []

          with open(content_file) as fp:
            for i, line in enumerate(fp):
              info = line.strip().split(",")
              info = [float(x) for x in info]

              timestamp_data.append(info)

        timestamp_data = np.asarray(timestamp_data)
        timestamp_data = timestamp_data.transpose()
        tot_node = timestamp_data.shape[0]

        pos = float(timestamp_data.shape[1])
        pos_embd = self.getPositionEmbedding(pos)

        

        st_day -= 1

        timestamp = 24 * hr_sample

        ts_data = []
        ps_data = []
        for idx in range(st_day,en_day+1-day,1):

            st_point = idx*timestamp
            en_point = (idx+1)*timestamp

            last_hour = False
            for st in range(st_point, en_point):
                ts = []
                for nd in range(tot_node):
                    a = timestamp_data[nd][st: st + (day  * timestamp) :timestamp]

                    assert len(a) == day
                    if (st + (day-1) * timestamp + pred_len) >= len(timestamp_data[nd]):
                        last_hour = True
                        break

                    for pred in range(1,pred_len+1):
                      gt = timestamp_data[nd][st + (day-1) * timestamp + pred]
                      a = np.append(a, gt)

                    assert len(a) == (day+pred_len)
                    ts.append(a)

                if last_hour:
                    break
                ts = np.asarray(ts)
                pos_a = pos_embd[st: st + (day  * timestamp) :timestamp]
                pos_a = np.expand_dims(pos_a,axis=0)
                pos_a = np.repeat(pos_a,tot_node,axis=0)
                ps_data.append(pos_a)
                ts_data.append(ts)


        return ts_data,ps_data
    
    def load_adj(self,ds):
      W = self.load_PeMSD(self.config['file_path.'+ ds +'_cites'])
      adj_lists = defaultdict(set)
      for row in range(len(W)):
        adj_lists[row] = set()
        for col in range(len(W)):
          if float(W[row][col]) >0 :
            adj_lists[row].add(col)
            adj_lists[col].add(row)
      
      adj = torch.zeros((len(adj_lists),len(adj_lists)))
      for u in adj_lists:
        for v in adj_lists[u]:
            adj[u][v] = 1
            adj[v][u] = 1
      return adj
        

    def load_PeMSD(self,file_path, sigma2=0.1, epsilon=0.5, scaling=True):

      try:
          W = pd.read_csv(file_path, header=None).values
      except FileNotFoundError:
          print('ERROR: No File Found.')
      
      n = W.shape[0]
      W = W / 10000.
      W2, W_mask = W * W, np.ones([n, n]) - np.identity(n)

      return np.exp(-W2 / sigma2) * (np.exp(-W2 / sigma2) >= epsilon) * W_mask

# Utility Functions


def evaluate(test_nodes,labels, graphSage, regression, device,test_loss):


    models = [graphSage, regression]

    params = []
    for model in models:
        for param in model.parameters():
            if param.requires_grad:
                param.requires_grad = False
                params.append(param)

    
    val_nodes = test_nodes
    embs = graphSage(val_nodes,False)
    predicts = regression(embs)
    loss_sup = torch.nn.MSELoss()(predicts, labels)
    loss_sup /= len(val_nodes)
    test_loss += loss_sup.item()

    for param in params:
        param.requires_grad = True

    return predicts,test_loss

def RMSELoss(yhat,y):
    yhat = torch.FloatTensor(yhat)
    y = torch.FloatTensor(y)
    return torch.sqrt(torch.mean((yhat-y)**2)).item()


def mean_absolute_percentage_error(y_true, y_pred):

  y_true = np.asarray(y_true)
  y_pred = np.asarray(y_pred)

  return np.mean(np.abs((y_true - y_pred) / y_true)) * 100

# Downstream Task

class Regression(nn.Module):

    def __init__(self, emb_size, out_size):
        super(Regression, self).__init__()

        self.layer = nn.Sequential(nn.Linear(emb_size, emb_size),
                                nn.ReLU(),
                                nn.Linear(emb_size, out_size),
                                nn.ReLU()
                                )
            

        self.init_params()

    def init_params(self):
        for param in self.parameters():
            if len(param.size()) == 2:
                nn.init.xavier_uniform_(param)

    def forward(self, embds):
        logists = self.layer(embds)
        return logists

# GNN Layer

class GNNLayer(nn.Module):
    
    def __init__(self, out_size,num_layers): 
        super(GNNLayer, self).__init__()

        self.out_size = out_size
        
        dim = (num_layers+2) * self.out_size
        self.weight = nn.Parameter(torch.FloatTensor(out_size, dim))

        self.init_params()

    def init_params(self):
        for param in self.parameters():
            nn.init.xavier_uniform_(param)

    def forward(self, self_feats, aggregate_feats, his_feats, neighs=None):
        combined = torch.cat([self_feats, aggregate_feats, his_feats], dim=1)
        combined = F.relu(self.weight.mm(combined.t())).t()
        return combined

#Spatial GNN

class GNN(nn.Module):
  def __init__(self, num_layers,input_size,out_size, adj_lists, device):
    super(GNN, self).__init__()

    self.num_layers = num_layers
    self.input_size = input_size
    self.out_size = out_size
    self.adj_lists = []
    self.device = device
    
    _ones = torch.ones(adj_lists.shape).to(device)
    _zeros = torch.zeros(adj_lists.shape).to(device)

    setattr(self, 'layer_adj1', adj_lists)
    
    for index in range(2, num_layers+1):
      cur_adj = torch.pow(adj_lists,index)
      cur_adj = torch.where(cur_adj>0, _ones, _zeros)

      prev_adj = torch.pow(adj_lists,index-1)
      prev_adj = torch.where(prev_adj>0, _ones, _zeros)

      layer_adj = cur_adj - prev_adj
      setattr(self, 'layer_adj'+str(index), layer_adj)
      
    self.GNN_Layer = GNNLayer(out_size, num_layers)

  def forward(self, nodes_batch,ts):

    pre_hidden_embs = self.raw_features
    nb = nodes_batch

    aggregated_feats = []
    for index in range(1, self.num_layers+1):
      neigh_feats = self.aggregate(nb, pre_hidden_embs,index)        
      aggregated_feats.append(neigh_feats)
    
    aggregated_feats = torch.cat(aggregated_feats,dim=1)

    cur_hidden_embs = self.GNN_Layer(pre_hidden_embs,aggregated_feats, self.pre_latent_feats)

    pre_hidden_embs = cur_hidden_embs
    
    return pre_hidden_embs

  def aggregate(self, nodes,pre_hidden_embs,layer):
      
    embed_matrix = pre_hidden_embs
    mask = getattr(self, 'layer_adj'+str(layer))

    num_neigh = mask.sum(1, keepdim=True)
    _ones = torch.ones(num_neigh.shape).to(self.device)
    num_neigh = torch.where(num_neigh>0,num_neigh,_ones)
    mask = mask.div(num_neigh)

    aggregate_feats = mask.mm(embed_matrix) 
          
    return aggregate_feats

"""# Data Loader"""

class DataLoader:

  def __init__(self, config,ds,pred_len):
    
    super(DataLoader, self).__init__()

    self.ds = ds
    self.dataCenter = DataCenter(config)

    if ds == "PeMSD7":
      train_st = 1
      train_en = 22

      test_st = 23
      test_en = 44 
      
    elif ds == "PeMSD8":
      train_st = 1
      train_en = 50

      test_st = 51
      test_en = 62 
    
    elif ds == "PeMSD4" :
      train_st = 1
      train_en = 47

      test_st = 48
      test_en = 58
  
    self.train_st = train_st
    self.train_en = train_en
    self.test_st = test_st
    self.test_en = test_en

    self.hr_sample = 12
    self.day = 8
    self.pred_len = pred_len
    
  def load_data(self):
    print("Loading Data...")
    train_data,train_pos = self.dataCenter.load_data(self.ds,self.train_st,self.train_en,self.hr_sample,self.day,self.pred_len)
    test_data,test_pos = self.dataCenter.load_data(self.ds,self.test_st,self.test_en,self.hr_sample,self.day,self.pred_len)
    adj = self.dataCenter.load_adj(self.ds)
    print("Data Loaded")
    print("Dataset: ", self.ds)
    print("Total Nodes: ",adj.shape[0])
    print("Train timestamps: ",len(train_data))
    print("Test timestamps: ",len(test_data))
    print("Predicting After: ",self.pred_len*5,"minutes")

    return train_data,train_pos,test_data,test_pos,adj

"""# Traffic Model"""

class TrafficModel:

    def __init__(self, train_data,train_pos,test_data,test_pos,adj, 
                 config, ds, input_size, out_size,GNN_layers,
                epochs, device,num_timestamps, pred_len,save_flag,PATH,b_debug,t_debug):
      
      super(TrafficModel, self).__init__()
      
      
      self.train_data,self.train_pos,self.test_data,self.test_pos,self.adj = train_data,train_pos,test_data,test_pos,adj
      self.all_nodes = [i for i in range(self.adj.shape[0])]

      self.ds = ds
      self.input_size = input_size
      self.out_size = out_size
      self.GNN_layers = GNN_layers
      self.day = input_size 
      self.device = device
      self.epochs = epochs
      self.regression = Regression(input_size * num_timestamps, pred_len)
      self.num_timestamps = num_timestamps
      self.pred_len = pred_len

      self.node_bsz = 512
      self.PATH = PATH
      self.save_flag = save_flag

      self.train_data = torch.FloatTensor(self.train_data).to(device)
      self.test_data = torch.FloatTensor(self.test_data).to(device)
      self.train_pos = torch.FloatTensor(self.train_pos).to(device)
      self.test_pos = torch.FloatTensor(self.test_pos).to(device)
      self.all_nodes = torch.LongTensor(self.all_nodes).to(device)
      self.adj = torch.FloatTensor(self.adj).to(device)

      self.b_debug = b_debug
      self.t_debug = t_debug
      
    def run_model(self):


      timeStampModel = CombinedGNN(self.input_size,self.out_size,self.adj, 
      self.device,self.train_data,self.train_pos,self.test_data,self.test_pos,1,self.GNN_layers,self.num_timestamps,self.day)
      timeStampModel.to(self.device)

      regression = self.regression
      regression.to(self.device)

      min_RMSE = float("Inf") 
      min_MAE = float("Inf") 
      min_MAPE = float("Inf")
      best_test = float("Inf")
      
      lr = 0.001
      # if self.ds == "PeMSD7":
        # lr = 0.001
      # elif self.ds == "PeMSD8":
      #   lr = 0.0001
        
      train_loss = torch.tensor(0.).to(self.device)  
      
      for epoch in range(1,epochs):

        print("Epoch: ",epoch," running...")

        tot_timestamp = len(self.train_data)
        if self.t_debug:
            tot_timestamp = 120
        idx = np.random.permutation(tot_timestamp+1-self.num_timestamps)

        for data_timestamp in idx:

          timeStampModel, regression, train_loss = apply_model(self.all_nodes,timeStampModel, 
          regression, data_timestamp,self.node_bsz, self.device,
          self.pred_len,self.train_data,self.num_timestamps,self.day,train_loss,lr)
        
          if self.b_debug:
            break

        train_loss /= len(idx)
        # if self.ds=="PeMSD7":
        if epoch<= 24 and epoch%8==0:
          lr *= 0.5
        else:
          lr = 0.0001


        print("Train avg loss: ",train_loss)


        pred = []
        label = []
        tot_timestamp = len(self.test_data)
        if self.t_debug:
            tot_timestamp = 120
        idx = np.random.permutation(tot_timestamp+1-self.num_timestamps)
        test_loss = torch.tensor(0.).to(self.device)
        for data_timestamp in idx:

          #window slide
          timeStampModel.st = data_timestamp

          #test_label
          raw_features = self.test_data[timeStampModel.st+self.num_timestamps-1]
          test_label = raw_features[:,self.day:]
          
          #evaluate
          temp_predicts,test_loss = evaluate(self.all_nodes,test_label, timeStampModel, regression, 
                  self.device,test_loss)

          label = label + test_label.detach().tolist()
          pred = pred + temp_predicts.detach().tolist()
            
          if self.b_debug:
            break

        
        test_loss /= len(idx)
        print("Average Test Loss: ",test_loss)

        

        RMSE = torch.nn.MSELoss()(torch.FloatTensor(pred), torch.FloatTensor(label))
        RMSE = torch.sqrt(RMSE).item()
        MAE = mean_absolute_error(pred,label)
        MAPE = mean_absolute_percentage_error(label,pred)

        if test_loss <= best_test:
          best_test = test_loss
          pred_after = self.pred_len * 5
          min_RMSE = RMSE
          min_MAE = MAE
          min_MAPE = MAPE
          if self.save_flag:
              torch.save(timeStampModel, self.PATH + "/" + self.ds + "/bestTmodel_" + str(pred_after) +"minutes.pth")
              torch.save(regression, self.PATH + "/" + self.ds + "/bestRegression_" + str(pred_after) +"minutes.pth")
          
        
        
        print("Epoch:", epoch)
        print("RMSE: ", RMSE)
        print("MAE: ", MAE)
        print("MAPE: ", MAPE)
        print("===============================================")

        
        print("Min RMSE: ", min_RMSE)
        print("Min MAE: ", min_MAE)
        print("Min MAPE: ", min_MAPE)
        
        print("===============================================")



      return
    
    def run_Trained_Model(self):
      pred_after = self.pred_len * 5
      timeStampModel = torch.load(self.PATH + "/saved_model/" + self.ds +  "/bestTmodel_" + str(pred_after) +"minutes.pth")
      regression = torch.load(self.PATH + "/saved_model/" + self.ds +  "/bestRegression_" + str(pred_after) +"minutes.pth")
      pred = []
      label = []
      tot_timestamp = len(self.test_data)
      idx = np.random.permutation(tot_timestamp+1-self.num_timestamps)
      test_loss = torch.tensor(0.).to(self.device)
      for data_timestamp in idx:

        #window slide
        timeStampModel.st = data_timestamp

        #test_label
        raw_features = self.test_data[timeStampModel.st+self.num_timestamps-1]
        test_label = raw_features[:,self.day:]
        
        #evaluate
        temp_predicts,test_loss = evaluate(self.all_nodes,test_label, timeStampModel, regression, 
                self.device,test_loss)

        label = label + test_label.detach().tolist()
        pred = pred + temp_predicts.detach().tolist()

      
      test_loss /= len(idx)
      print("Average Test Loss: ",test_loss)

      
      RMSE = torch.nn.MSELoss()(torch.FloatTensor(pred), torch.FloatTensor(label))
      RMSE = torch.sqrt(RMSE).item()
      MAE = mean_absolute_error(pred,label)
      MAPE = mean_absolute_percentage_error(label,pred)
      
      
      print("RMSE: ", RMSE)
      print("MAE: ", MAE)
      print("MAPE: ", MAPE)
      print("===============================================")

# Combined GraphSAGE

class CombinedGNN(nn.Module):
    def __init__(self,input_size,out_size, adj_lists,
                 device,train_data,train_pos,test_data,test_pos,
                 st,GNN_layers,num_timestamps,day):
        super(CombinedGNN, self).__init__()

        self.train_data = train_data
        self.train_pos = train_pos
        self.test_data = test_data
        self.test_pos = test_pos
        self.st = st
        self.num_timestamps = num_timestamps
        self.out_size = out_size
        self.tot_nodes = adj_lists.shape[0]
        self.device = device
        self.adj_lists = adj_lists

        
        self.day = day
  
        for timestamp in range(0, self.num_timestamps):

            setattr(self, 'his_model' + str(timestamp),GNN(GNN_layers,input_size-1,
            out_size-1,adj_lists,device))

            setattr(self, 'cur_model' + str(timestamp),GNN(GNN_layers,1,
            1,adj_lists,device))

                
        self.his_weight = nn.Parameter(torch.FloatTensor(out_size-1, self.num_timestamps*out_size-1))
        self.cur_weight = nn.Parameter(torch.FloatTensor(1, self.num_timestamps*1))

        dim = self.num_timestamps*out_size
        self.final_weight = nn.Parameter(torch.FloatTensor(dim,dim))

        self.init_params()

    def init_params(self):
      for param in self.parameters():

          if(len(param.shape)>1):
            nn.init.xavier_uniform_(param)


    def forward(self,nodes_batch,isTrain):

        his_timestamp_embds = torch.zeros((nodes_batch.shape[0],self.out_size-1)).to(self.device)
        cur_timestamp_embds = torch.zeros((nodes_batch.shape[0],1)).to(self.device)


        historical_embds = []
        current_embds = []

        for timestamp in range(0, self.num_timestamps):


            historicalModel = getattr(self, 'his_model' + str(timestamp))
            historicalModel.adj_lists = self.adj_lists
            setattr(historicalModel, 'timestamp_no', timestamp)
            setattr(historicalModel, 'pre_latent_feats', his_timestamp_embds)

            if isTrain:
                his_raw_features = self.train_data[self.st+timestamp]
                his_pos = self.train_pos[self.st+timestamp]
            else:
                his_raw_features = self.test_data[self.st+timestamp]
                his_pos = self.test_pos[self.st+timestamp]

            his_raw_features = his_raw_features[:,:self.day-1]
            his_pos = his_pos[:,:self.day-1]
            setattr(historicalModel,'raw_features',his_raw_features)
            

            his_timestamp_embds = historicalModel(nodes_batch,timestamp) + his_pos
            
            historical_embds.append(his_timestamp_embds)
            upto_current_timestamp = torch.cat(historical_embds,dim=1)
            weight = self.his_weight[:,:(timestamp+1)*(self.out_size-1)]
            his_timestamp_embds = F.relu(weight.mm(upto_current_timestamp.t())).t()

            currentModel = getattr(self, 'cur_model' + str(timestamp))
            currentModel.adj_lists = self.adj_lists
            setattr(currentModel, 'timestamp_no', timestamp)
            setattr(currentModel, 'pre_latent_feats', cur_timestamp_embds)

            if isTrain:
                cur_raw_features = self.train_data[self.st+timestamp]
                cur_pos = self.train_pos[self.st+timestamp]
            else:
                cur_raw_features = self.test_data[self.st+timestamp]
                cur_pos = self.test_pos[self.st+timestamp]

            cur_raw_features = cur_raw_features[:,self.day-1:self.day]
            cur_pos = cur_pos[:,self.day-1:self.day]
            setattr(currentModel,'raw_features',cur_raw_features)

            cur_timestamp_embds = currentModel(nodes_batch,timestamp) + cur_pos

            current_embds.append(cur_timestamp_embds)
            upto_current_timestamp = torch.cat(current_embds,dim=1)
            weight = self.cur_weight[:,:(timestamp+1)*1]
            cur_timestamp_embds = F.relu(weight.mm(upto_current_timestamp.t())).t()


        his_final_embds = torch.cat(historical_embds,dim=1)
        cur_final_embds = torch.cat(current_embds,dim=1)

        final_embds = [his_final_embds,cur_final_embds]
        final_embds = torch.cat(final_embds,dim=1)
        final_embds = F.relu(self.final_weight.mm(final_embds.t()).t())
        
        return final_embds

# Applying Model

def apply_model(train_nodes, CombinedGNN, regression, data_timestamp, 
                node_batch_sz, device,pred_len,train_data,num_timestamps,day,avg_loss,lr):


    models = [CombinedGNN, regression]
    params = []
    for model in models:
      for param in model.parameters():
          if param.requires_grad:
              params.append(param)



    optimizer = torch.optim.Adam(params, lr=lr, weight_decay=0)

    optimizer.zero_grad()  # set gradients in zero...
    for model in models:
      model.zero_grad()  # set gradients in zero

    node_batches = math.ceil(len(train_nodes) / node_batch_sz)

    loss = torch.tensor(0.).to(device)
    #window slide
    CombinedGNN.st = data_timestamp
    #test_label
    raw_features = train_data[CombinedGNN.st+num_timestamps-1]
    labels = raw_features[:,day:]
    for index in range(node_batches):

      nodes_batch = train_nodes[index * node_batch_sz:(index + 1) * node_batch_sz]
      nodes_batch = nodes_batch.view(nodes_batch.shape[0],1)
      labels_batch = labels[nodes_batch]      
      labels_batch = labels_batch.view(len(labels_batch),pred_len)
      embs_batch = CombinedGNN(nodes_batch,True)  # Finds embeddings for all the ndoes in nodes_batch

      logists = regression(embs_batch)


      loss_sup = torch.nn.MSELoss()(logists, labels_batch)

      loss_sup /= len(nodes_batch)
      loss += loss_sup



    avg_loss += loss.item()

    loss.backward()
    for model in models:
      nn.utils.clip_grad_norm_(model.parameters(), 5) 
    optimizer.step()

    optimizer.zero_grad()
    for model in models:
      model.zero_grad()

    return CombinedGNN, regression,avg_loss

# Main Function

parser = argparse.ArgumentParser(description='pytorch version of Traffic Forecasting GNN')
parser.add_argument('-f')  


parser.add_argument('--dataset', type=str, default='PeMSD7')
parser.add_argument('--GNN_layers', type=int, default=3)
parser.add_argument('--num_timestamps', type=int, default=12)
parser.add_argument('--pred_len', type=int, default=9)
parser.add_argument('--epochs', type=int, default=200)
parser.add_argument('--seed', type=int, default=42)
parser.add_argument('--cuda', action='store_true',help='use CUDA')
parser.add_argument('--trained_model', action='store_true')
parser.add_argument('--save_model', action='store_true')
parser.add_argument('--input_size', type=int, default=8)
parser.add_argument('--out_size', type=int, default=8)



args = parser.parse_args()

args.cuda = False

if torch.cuda.is_available():
	if not args.cuda:
		print("WARNING: You have a CUDA device, so you should run with --cuda")
	else:
		device_id = torch.cuda.current_device()
		print('using device', device_id, torch.cuda.get_device_name(device_id))

device = torch.device("cuda" if args.cuda else "cpu")
print('DEVICE:', device)

 
if __name__ == '__main__':

    print('Traffic Forecasting GNN with Historical and Current Model')

    #set user given seed to every random generator
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)

    PATH = os.getcwd() + "/"
    config_file = PATH + "experiments.conf"
 
    config = pyhocon.ConfigFactory.parse_file(config_file)
    ds = args.dataset
    pred_len = args.pred_len
    data_loader = DataLoader(config,ds,pred_len)
    train_data,train_pos,test_data,test_pos,adj = data_loader.load_data()

    num_timestamps = args.num_timestamps 
    GNN_layers = args.GNN_layers
    input_size = args.input_size
    out_size = args.input_size
    epochs = args.epochs
    save_flag = False

b_debug = False
t_debug = False

hModel = TrafficModel (train_data,train_pos,test_data,test_pos,adj,config, ds, input_size, out_size,GNN_layers,
                epochs, device,num_timestamps,pred_len,save_flag,PATH,b_debug,t_debug)
if not args.trained_model: #train model and evaluate
    hModel.run_model()
else:
    print("Running Trained Model...")
    hModel.run_Trained_Model() #run trained model


