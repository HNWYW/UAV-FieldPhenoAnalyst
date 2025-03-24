# coding: utf-8
# The code is written by Linghui

from difflib import get_close_matches
# from selectors import EpollSelector
import numpy as np
import matplotlib.pyplot as plt
import cv2
from PIL import Image
from skimage import data
from math import floor, ceil
# from skimage.feature import greycomatrix, greycoprops
import skimage.feature
# from sklearn.metrics import hamming_loss
import copy


def main():
    pass

def image_patch(img2, slide_window, h, w):

    image = img2
    window_size = slide_window
    patch = np.zeros((slide_window, slide_window, h, w), dtype=np.uint8)
    
    # 2,3对应的是h,w,shape反映的是数组的维数
    for i in range(patch.shape[2]):
        for j in range(patch.shape[3]):
            patch[:, :, i, j] = img2[i : i + slide_window, j : j + slide_window]
 
    return patch   


def calcu_glcm(img, mi, ma, nbit, slide_window, step, angle):

    h, w = img.shape

    # Compressed gray range：vmin: 0-->0, vmax: 256-1 -->nbit-1
    # 灰度量化过程256--64  64级的灰度量化的过程为0-63
    # np.linspace生成等差数列
    # np.digitize功能：返回一个和x形状相同的数据，返回值中的元素为对应x位置的元素落在bins中区间的索引号
    bins = np.linspace(mi, ma+1, nbit+1)
    img1 = np.digitize(img, bins) - 1
    # img1 = np.digitize(img, bins)

    # (512, 512) --> (slide_window, slide_window, 512, 512)
    img2 = cv2.copyMakeBorder(img1, floor(slide_window/2), floor(slide_window/2)
                              , floor(slide_window/2), floor(slide_window/2), cv2.BORDER_REPLICATE) # 图像扩充
                            #   cv2.BORDER_CONSTANT, value=0) # 图像扩充
    
    # cv2.BORDER_REPLICATE
    patch = np.zeros((slide_window, slide_window, h, w), dtype=np.uint8)
    patch = image_patch(img2, slide_window, h, w)

    # Calculate GLCM (5, 5, 512, 512) --> (64, 64, 512, 512)
    # greycomatrix(image, distances, angles, levels=None, symmetric=False, normed=False)
    # 得到共生矩阵，参数：图像矩阵，距离，方向，灰度级别，是否对称，是否标准化
    # glcm = np.zeros((nbit, nbit, len(step), len(angle), h, w), dtype=np.uint8)
    glcm = np.zeros((nbit, nbit, len(step), len(angle), h, w), dtype=np.float32)
    
    for i in range(patch.shape[2]):
        for j in range(patch.shape[3]):
            # glcm[:, :, :, :, i, j]= greycomatrix(patch[:, :, i, j], step, angle, levels=nbit,symmetric=True,normed=True)False
            glcm[:, :, :, :, i, j]= skimage.feature.graycomatrix(patch[:, :, i, j], step, angle, levels=nbit,symmetric=True,normed=True)

    return glcm

def calcu_glcm_mean(glcm, nbit):
    '''
    calc glcm mean
    '''
    # glcm对应的是灰度共生矩阵中的一个值  因此让它等于0是错的，应该是原始像素值等于0
    mean = np.zeros((glcm.shape[2], glcm.shape[3]), dtype=np.float32)
    for i in range(nbit):
        for j in range(nbit):    
            mean += glcm[i,j] * i 
    return mean 

def calcu_glcm_variance(glcm, nbit):
    '''
    calc glcm variance
    '''
    mean = np.zeros((glcm.shape[2], glcm.shape[3]), dtype=np.float32)
    for i in range(nbit):
        for j in range(nbit):
            # mean += glcm[i, j] * i / (nbit)**2
            mean += glcm[i, j] * i 

    variance = np.zeros((glcm.shape[2], glcm.shape[3]), dtype=np.float32)
    for i in range(nbit):  
        for j in range(nbit):
            variance += glcm[i, j] * (i - mean)**2

    return variance 

def calcu_glcm_homogeneity(glcm, nbit):
    '''
    calc glcm Homogeneity
    '''
    Homogeneity = np.zeros((glcm.shape[2], glcm.shape[3]), dtype=np.float32)
    for i in range(nbit):
        for j in range(nbit):
            Homogeneity += glcm[i,j] / (1.+(i-j)**2)

    return Homogeneity

def calcu_glcm_contrast(glcm, nbit):
    '''
    calc glcm contrast
    '''
    contrast = np.zeros((glcm.shape[2], glcm.shape[3]), dtype=np.float32)
    for i in range(nbit):
        for j in range(nbit):
            contrast += glcm[i, j] * ((i-j)**2)

    return contrast

def calcu_glcm_dissimilarity(glcm, nbit):
    '''
    calc glcm dissimilarity
    '''
    dissimilarity = np.zeros((glcm.shape[2], glcm.shape[3]), dtype=np.float32)
    for i in range(nbit):
        for j in range(nbit):
            dissimilarity += glcm[i, j] * np.abs(i-j)

    return dissimilarity

def calcu_glcm_entropy(glcm, nbit):
    '''
    calc glcm entropy 
    '''
    eps = 0.00001 
    # 因为背景为0值，而glcm不能为0，因此设定eps为0.00001值
    # a=np.zeros((64,64))
    entropy = np.zeros((glcm.shape[2], glcm.shape[3]), dtype=np.float32)
    glcm_log = np.zeros((glcm.shape[2], glcm.shape[3]), dtype=np.float32)
    
    
    for i in range(nbit):
        for j in range(nbit):
            
            glcm[i, j][glcm[i, j]==0] = 0.00001
            
            glcm_log = copy.deepcopy(glcm[i, j])
            
            glcm[i, j][glcm[i, j]==0.00001] = 0 
            
            entropy += -glcm[i, j] * np.log(glcm_log)

    return entropy


def calcu_glcm_correlation(glcm, nbit):
    
    '''
    calc glcm correlation (Unverified result)
    '''
    eps = 0.00001 
    mean_x = np.zeros((glcm.shape[2], glcm.shape[3]), dtype=np.float32)
    for i in range(nbit):
        for j in range(nbit):
            mean_x += glcm[i, j] * i 
            
    mean_y = np.zeros((glcm.shape[2], glcm.shape[3]), dtype=np.float32)
    for i in range(nbit):
        for j in range(nbit):
            mean_y += glcm[i, j] * j
    
    variance_x = np.zeros((glcm.shape[2], glcm.shape[3]), dtype=np.float32)
    for i in range(nbit):
        for j in range(nbit):
            variance_x += glcm[i, j] * (i - mean_x)**2
            
    variance_y = np.zeros((glcm.shape[2], glcm.shape[3]), dtype=np.float32)
    for i in range(nbit):
        for j in range(nbit):
            variance_y += glcm[i, j] * (j - mean_y)**2
    
    
    ppo = np.zeros((glcm.shape[2], glcm.shape[3]), dtype=np.float32)
    for i in range(nbit):
        for j in range(nbit):
            ppo += glcm[i, j]*i*j 
            
    correlation = np.zeros((glcm.shape[2], glcm.shape[3]), dtype=np.float32)
    correlation = (ppo-(mean_x*mean_y))/((np.sqrt(variance_x)*np.sqrt(variance_y))+eps)
            

    return correlation

 
def calcu_glcm_Second_Moment(glcm, nbit):
    '''
    
    calc glcm Second_Moment
    
    '''
    Second_Moment = np.zeros((glcm.shape[2], glcm.shape[3]), dtype=np.float32)
    for i in range(nbit):
        for j in range(nbit):
            Second_Moment += glcm[i, j]**2
            # Second_Moment += glcm[i, j]

    return Second_Moment



def calcu_txt_mean(txt_img,t):

    # 全部数值相加
    all_sum=np.sum(txt_img)
    
    # 非t值的个数
    Non_t_value=txt_img.size-np.sum(txt_img==t)
    
    ## 全部元素之和除以非0值的个数得到均值
    #txt_mean = (all_sum/Non_t_value)
    # 全部元素之和减去所有t值之和得到非t值之和，除以非t值的个数得到均值
    txt_mean = (all_sum-(t*np.sum(txt_img==t)))/Non_t_value
        
    return txt_mean
 
    
def Edge_Remove(data,value):
    
    # 矩阵转数组
    data = np.array(data)
    
    # 矩阵左右边界增加0行
    h=np.full((data.shape[0],1),0)
    data=np.column_stack((h,data))
    data=np.column_stack((data,h))
    
    
    # 增加首尾0行
    t=np.full((1, data.shape[1]),value)
    data=np.row_stack((data,t))
    data=np.row_stack((t,data))
    
    
    
    row_2=data.shape[0]
    column_2=data.shape[1]
    
    # 转换为一行
    data=data.reshape(1,-1)


    list1=[]
    list2=[]
    
    # loop序号
    loop_n1=data.size-1
    # 横向边界值去除numpy: np.logical_and/or/not (逻辑与/或/非)
    for i in range(loop_n1):
        if  np.logical_and(data[0,i]== value , data[0,i+1] != value):
            list1.append(i)


    for i in range(loop_n1):
        if  np.logical_and(data[0,i] != value , data[0,i+1] == value):
            list2.append(i)


    for t in range(len(list1)):
        data[0,list1[t]+1]=value
        data[0,list1[t]+2]=value
        data[0,list1[t]+3]=value
        data[0,list1[t]+4]=value
        data[0,list1[t]+5]=value
        data[0,list1[t]+6]=value
        data[0,list1[t]+7]=value
        data[0,list1[t]+8]=value
        data[0,list1[t]+9]=value
        data[0,list1[t]+10]=value
        data[0,list1[t]+11]=value


    for t in range(len(list2)):
        data[0,list2[t]]=value
        data[0,list2[t]-1]=value
        data[0,list2[t]-2]=value
        data[0,list2[t]-3]=value
        data[0,list2[t]-4]=value
        data[0,list2[t]-5]=value
        data[0,list2[t]-6]=value
        data[0,list2[t]-7]=value
        data[0,list2[t]-8]=value
        data[0,list2[t]-9]=value
        data[0,list2[t]-10]=value

    # 转换为原来的尺寸
    data=data.reshape(row_2,column_2)
    
    # 转置
    data=data.T
    
    # 准换为一行
    data=data.reshape(1,-1)

    list3=[]
    list4=[]
     
    # loop序号
    loop_n2=data.size-1
    for i in range(loop_n2):
        if  np.logical_and(data[0,i]== value , data[0,i+1] != value):
        # if data[i] == value  and  data[i+1] != value:
            list3.append(i)

    for i in range(loop_n2):
        if  np.logical_and(data[0,i] != value , data[0,i+1] == value):
            list4.append(i)


    for t in range(len(list3)):
        
        data[0,list3[t]+1]=value
        data[0,list3[t]+2]=value
        data[0,list3[t]+3]=value
        data[0,list3[t]+4]=value
        data[0,list3[t]+5]=value
        data[0,list3[t]+6]=value
        data[0,list3[t]+7]=value
        data[0,list3[t]+8]=value
        data[0,list3[t]+9]=value
        data[0,list3[t]+10]=value
        data[0,list3[t]+11]=value

    for t in range(len(list4)):
        
        data[0,list4[t]]=value
        data[0,list4[t]-1]=value
        data[0,list4[t]-2]=value
        data[0,list4[t]-3]=value
        data[0,list4[t]-4]=value
        data[0,list4[t]-5]=value
        data[0,list4[t]-6]=value
        data[0,list4[t]-7]=value
        data[0,list4[t]-8]=value
        data[0,list4[t]-9]=value
        data[0,list4[t]-10]=value
        
    data_final=data.reshape(column_2,row_2).T
    
    return data_final


if __name__ == '__main__':
    main()
    
