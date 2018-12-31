'''
This module provides functions about filling path generation
# 1. extract contours tree from mask image [simulating a layer of slices in STL model].
# 2. for each seperated region, generate iso-contours.
# 3. connect iso-contour to fermal spirals.
example:
          pe = pathEngine()
          im, contours, areas, hiearchy, root_contour_idx = pe.generate_contours_from_img(filename, isRevertBlackWhite)  
          contour_tree = pe.convert_hiearchy_to_PyPolyTree()
          pe.traversing_PyPolyTree(contour_tree)
          group_contour = get_contours_from_each_connected_region(contour_tree, '0')
          for e in group_contour.values():
              ePath = gen_isocontours(e)
              ePath = gen_fermat_curve(ePath)

In 3D printing path generation,   
'''

import cv2
import numpy as np
import pyclipper
import math
import scipy.spatial.distance as scid
import suGraph
from scipy.signal import savgol_filter
'''
Hold path info and visualization functions for 2D slice
@contour_tree:   
'''
class suPath2D():
    def __init__(self):        
        self.contour_tree      = None
        self.group_boundary    = []
        self.group_isocontours = []  #containts iso contours list
        self.group_isocontours_2D = []
        self.group_relationship_matrix = []
        
        return
    ##################################################################
    # Get a 1D global index from iso_contours list contour(i,j), where
    # i is the distance to the boundary, there are many contours(j=0...n-1).  
    # Thus we can generate a index matrix for building a graph that can
    # be visualized in different tools.
    # Mathematica:
    #    GraphPlot[{{1, 1, 1, 0}, {1, 0, 0, 0}, {0, 1, 0, 0}, {1, 1, 0, 1}},
    #               SelfLoopStyle -> True, MultiedgeStyle -> True,
    #               VertexLabeling -> True, DirectedEdges -> True]
    ##################################################################   
    def get_contour_id(self,i,j,iso_contours):
        id = 0 
        ii = 0
        for cs in iso_contours:
            if ii == i: break
            for c in cs:
                id += 1
            ii += 1           
        id += j # indexed from 0
        return id   
    def prev_idx(self, idx, contour):    
        if idx > 0:
            return idx - 1;
        if idx == 0:
            return len(contour) -1
    
    def next_idx(self, idx, contour):
        if idx < len(contour)-1:
            return idx + 1
        if idx == len(contour) - 1:
            return 0    
    ####################################
    # draw poly line to image #
    # point_list is n*2 np.ndarray #
    ####################################
    def draw_line(self, point_lists, img, color, line_width=1, point_size=0):
        point_lists = point_lists.astype(int)
        pts = point_lists.reshape((-1,1,2))
        cv2.polylines(img, [pts], False, color, thickness=line_width, lineType=cv2.LINE_AA)
        #cv2.imshow("Art", img)
        if point_size != 0:
            for p in point_lists:
                cv2.circle(img, tuple(p), point_size, color)   
        return
    def draw_text(self, text, bottom_left, img, fontColor = (255,0,0), fontScale = 0.5, lineType=1):
        font                   = cv2.FONT_HERSHEY_SIMPLEX
        fontSize               = [12,-12]
        offset = bottom_left - np.array(fontSize)*fontScale
        cv2.putText(img,text,
            tuple(offset.astype(int)) ,
            font,
            fontScale,
            fontColor,
            lineType)
        return
    #################################
    # Generate N color list
    #################################
    def generate_RGB_list(self, N):
        import colorsys
        HSV_tuples = [(x*1.0/N, 0.8, 0.9) for x in range(N)]
        RGB_tuples = map(lambda x: colorsys.hsv_to_rgb(*x), HSV_tuples)
        rgb_list = tuple(RGB_tuples)
        return np.array(rgb_list) * 255   
    
    
class pathEngine:
    def __init__(self):
        self.offset = 0.4
        self.im = None
        self.contours = None
        self.areas = None
        self.hiearchy = None 
        self.path2d = suPath2D()
        self.root_of_region_contour = None
        self.iso_contours_of_a_region = []
        return
    
    #######################################################################################
    # return contours(python list by a tree) #
    # https://docs.opencv.org/trunk/d9/d8b/tutorial_py_contours_hierarchy.html
    # This function provides:
    # 1. Compute area for each contour
    # 2. Return image, contours, areas, hiearchy, root_contour_idx
    #######################################################################################
    def generate_contours_from_img(self, imagePath, isRevertImage=False):          
        im = cv2.imread(imagePath, cv2.IMREAD_GRAYSCALE)
        if isRevertImage :
            im = 255 - im
        ret, thresh = cv2.threshold(im, 127, 255, 1)
       
        self.im, self.contours, self.hiearchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        return self.im, self.contours, self.hiearchy
    #######################################################################################
    # Recursively add a child node and add a brother node by info from hiearchy
    # In each node, the contour from opencv is converted from (x,1,2) to (x,2)
    # @cur_node: current node, first input is a empty root node
    # @idx: current index   
    # ref: https://docs.opencv.org/trunk/d9/d8b/tutorial_py_contours_hierarchy.html
    #######################################################################################
    def recusive_add_node(self, node, idx):
       
        if idx >= self.hiearchy.shape[1]:
            return
        Next, Previous, First_Child, Parent = self.hiearchy[0][idx]   
        new_node = pyclipper.PyPolyNode()
        new_node.IsOpen = False
        new_node.IsHole = False   
        # add new node
        if First_Child != -1:
            new_node.Contour = self.contours[First_Child].reshape((-1,2)) # (x rows, 1, 2) -> (x rows, 2)               
            new_node.Parent = node
            node.Childs.append(new_node)
            self.recusive_add_node(new_node, First_Child)
        if Next != -1:
                new_node.Contour = self.contours[Next].reshape((-1,2))
                new_node.Parent = node.Parent
                new_node.Parent.Childs.append(new_node)
                self.recusive_add_node(new_node, Next)    
        return   
    ###############################################################################
    # Generate hiearchy tree from contours and hiearchy matrix
    # Return contour tree
    # 1. construct a root node
    # 2. find the first parent contour and add it to the first child node[use recusive_add_node].
    # ref: http://www.angusj.com/delphi/clipper/documentation/Docs/Units/ClipperLib/Classes/PolyTree/_Body.htm
    # ref: https://stackoverflow.com/questions/32182544/pyclipper-crash-on-trivial-case-terminate-called-throwing-an-exception   
    ###############################################################################
    def convert_hiearchy_to_PyPolyTree(self):
        if self.hiearchy == None:
            return
        # find first contour in hiearchy-0
        root = pyclipper.PyPolyNode()
        idx = -1
        for row in self.hiearchy[0]:
            Next, Previous, First_Child, Parent = row
            if Previous == -1 and Parent == -1:
                idx += 1
                node = pyclipper.PyPolyNode()
                node.Parent = root        
                node.Contour = self.contours[idx].reshape((-1,2))  # (x rows, 1, 2) -> (x rows, 2)                   
                node.IsOpen = False
                node.IsHole = False               
                root.Childs.append(node)
                self.recusive_add_node(node, idx)
                break
        self.root_of_region_contour = root
        return root  
   
    ################################################################################
    # for each seperated region on a slice
    #  - return contour group to reprent boundaries of a region
    # The seperated region means a region with connected area.
    # @polyTreeNode is used to hold region boundary. Typically, the boundaries
    #               stored in the current node represent external contours, and
    #               the contours stored in the child nodes represent the internal
    #               contours, such as holes. If child nodes have their own children
    #               that will represent new seperated regions. We can deal these cases
    #               by the recursive process.
    # @sId is the id of polyTreeNode, eg. 0(root), 0-1(first child of root),
    #               0-1-2(second gradson of root)
    # @return a dict, @contour_group, each key-value represents a seperate regon KEY
    #              and its boundary contours.
    # examples:    contour_group = get_contours_from_each_connected_region(root, '0')
    #              contour_group = get_contours_from_each_connected_region(node, '0-1-1')
    ################################################################################
    def get_contours_from_each_connected_region(self, polyTreeNode, sId = '0'):
        root = polyTreeNode
        contour_group = {}  # eg. contour_group[id] holds all inner and outter contours in a seperated region.
        nDeep = sId.count('-')                       
        #for root node
        if (nDeep == 0):
            iChild = 0
            for n in polyTreeNode.Childs:
                cur_id = sId + '-' + str(iChild)
                cGroup = self.get_contours_from_each_connected_region(n, cur_id)
                # merge dict to contour_group
                contour_group.update(cGroup)  
                iChild += 1
        #for layer contains outer contour
        if (nDeep % 2 == 1):
            iChild = 0       
            contours = []
            contours.append(polyTreeNode.Contour) #outer contour
            #for layers contains inner contour
            for n in polyTreeNode.Childs:
                cur_id = sId + '-' + str(iChild)
                contours.append(n.Contour)
                iChild += 1           
                #next layer
                ii = 0
                for c in n.Childs:
                        child_id = cur_id + '-' + str(ii)
                        cGroup = self.get_contours_from_each_connected_region(n, cur_id)
                        # merge dict to contour_group
                        contour_group.update(cGroup) 
                        ii += 1               
            contour_group[sId] = contours       
           
        return contour_group   
   
    #######################################
    # Traversing a PyPolyTree
    # @root: root of tree
    # @order: 0-deep first, 1-breath first
    # @func: function(contour, Children_list)
    #######################################
    def traversing_PyPolyTree(self, root, func=None, order=0):
        if (func != None):           
            func(root)
        else:
            if(root.Parent == None):
                print("-----")
            msg = "Node {} has {} child node".format(root.depth, len(root.Childs))
            print(msg)
             
        if (order == 0 ):  # deep first
            for n in root.Childs:
                self.traversing_PyPolyTree(n, func, 0)
        return  
   
    #######################################
    # Get all nodes that depth = nDepth from a PyPolyTree
    # @depth: depth of node
    # return a list of node where node.depth = depth   
    #######################################   
    def get_nodes_by_layer(self, node, depth):
        node_list = []       
        def traverse(node,depth, node_list):
            for n in node.Childs:
                if (n.depth == depth):
                    node_list.append(n)
                    continue
                else:
                    traverse(n,depth,node_list)
            return
             
        traverse(node, depth, node_list)
        return node_list
           
   

    ##############################################
    # fill a region with iso contours
    # add all contours into self.iso_contours_of_a_region
    # return iso_contours_of_a_region, which inclues
    # an iso contour list, each is represented as c[i,j]
    # example:
    #          pe = pathEngine()
    #          pe.generate_contours_from_img(filepath, True)
    #          contour_tree = pe.convert_hiearchy_to_PyPolyTree() 
    #          group_contour = pe.get_contours_from_each_connected_region(contour_tree, '0')
    #          for cs in group_contour:
    #              pe.iso_contours_of_a_region.clear()
    #              iso_contours = pe.fill_closed_region_with_iso_contours(cs, offset)
    #              ...
    ##############################################
    def fill_closed_region_with_iso_contours(self, input_contours, offset):
        iso_contours_of_a_region = []
        contours = input_contours
        iso_contours_of_a_region.append(input_contours)
        while(len(contours) != 0):
            pco = pyclipper.PyclipperOffset()
            pco.AddPaths(contours, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
            contours = pco.Execute(offset)           
            iso_contours_of_a_region.append( contours)
        return iso_contours_of_a_region
    def prev_idx(self, idx, contour):   
        if idx > 0:
            return idx - 1;
        if idx == 0:
            return len(contour) -1
   
    def next_idx(self, idx, contour):
        if idx < len(contour)-1:
            return idx + 1
        if idx == len(contour) - 1:
            return 0   
    ##################################################################################################################
    # Resample a curve by Roy's method
    # "http://www.morethantechnical.com/2012/12/07/resampling-smoothing-and-interest-points-of-curves-via-css-in-opencv-w-code/"
    # @contour: input contour
    # @size: sample size on the contour
    # @is_open: True means openned polyline, False means closed polylien
    # example:
    #          c = resample_curve_by_equal_dist( c, nSample)
    ##################################################################################################################
    def resample_curve_by_equal_dist(self, contour, size, is_open = False):
        resample_c = []
        ## compute length of contour
        contour_length = 0;  
        contour = np.asarray(contour)
        for i in range(len(contour) - 1):
            d = np.linalg.norm(contour[i+1]-contour[i])
            contour_length += d
           
        if is_open == False:
            d = np.linalg.norm(contour[0] - contour[-1])
            contour_length += d
       
        resample_size = size 
        N = int(contour_length / resample_size)
        #if (N < len(contour)):
        #    return contour
       
        dist = 0             # dist = cur_dist_to_next_original_point + last_original_dist
        cur_id = 0           # for concise
        resample_c.append(contour[0])
       
        nCount = len(contour) - 1
        if is_open == False:     
            nCount = len(contour)
           
        for i in range(nCount):
            next_id = self.next_idx(cur_id, contour)
            last_dist = np.linalg.norm(contour[next_id]-contour[i])
            dist += last_dist    #current length
            if(dist >= resample_size):
                #put a point on line
                d_ = last_dist - (dist - resample_size)    #reserve size
                dir_ = contour[next_id] - contour[cur_id]
               
                new_point = contour[cur_id] + d_ * dir_ / np.linalg.norm(dir_)
                resample_c.append(new_point)
               
                dist = last_dist - d_  #remaining dist
               
                #if remaining dist to next point needs more sampling...
                while (dist - resample_size > 1e-3):
                    new_point = resample_c[-1] + resample_size * dir_ / np.linalg.norm(dir_)
                    resample_c.append(new_point)               
                    dist -= resample_size              
                   
            cur_id = next_id
        #print(resample_c)  
        return  np.asarray(resample_c)
   
    #######################################
    # find nearest index of point in a contour
    # @in: point value(not index), a contour
    # @out: the index of a nearest point
    #####################################
    def find_nearest_point_idx(self, point, contour):
        idx = -1
        distance = float("inf")   
        for i in range(0, len(contour)-1):        
            d = np.linalg.norm(point-contour[i])
            if d < distance:
                distance = d
                idx = i
        return idx   
    ##########################################################################
    #find an index of point from end, with distance larger than T
    #@in: current index of point, current contour, 
    #@in: T is a distance can be set to offset or offset/2 or 2 * offset
    ##########################################################################
    def find_point_index_by_distance(self, cur_point_index, cur_contour, T):
        T = abs(T)
        start_point = cur_contour[cur_point_index]
        idx_end_point = self.prev_idx(cur_point_index, cur_contour)
        
        end_point=[]        
        for ii in range(0,len(cur_contour)-1):
            end_point = cur_contour[idx_end_point]
            distance=np.linalg.norm(start_point-end_point)            
            if distance > T:           
                break
            else:           
                idx_end_point = self.prev_idx(idx_end_point, cur_contour)  
        return idx_end_point    
    ##############################################################
    # @in: iso contours, index of start point, offset
    # @out: a single poly
    # If you want connect in then connect out,
    # you can divide contours into two sets, and run it twice,
    # then connect them.
    ##############################################################
    def contour2spiral(self, contours, idx_start_point, offset):
        offset = abs(offset)
        cc = [] # contour for return
        N = len(contours)
        for i in range(N):
            contour1 = contours[i]        
            
            ## find end point(e1)
            idx_end_point = self.find_point_index_by_distance(idx_start_point, contour1, 2*offset)
            end_point = contour1[idx_end_point]
            
            # add contour segment to cc
            idx = idx_start_point
            while idx != idx_end_point:
                cc.append(contour1[idx])
                idx = self.next_idx(idx, contour1)   
            
            if(i == N-1): 
                break
            
            ## find s2   
            idx_start_point2 = self.find_nearest_point_idx(end_point, contours[i+1])         
            
            idx_start_point = idx_start_point2   
            
            
        return cc     
    
    def connect_spiral(self, first_spiral, second_spiral, is_flip=True):
        s = []
        if is_flip:
            second_spiral = np.flip(second_spiral, 0)
            
        for i in range(len(first_spiral)):
            s.append(first_spiral[i])                 
        for i in range(len(second_spiral)):
            s.append(second_spiral[i])
        return s
    

    def smooth_curve_by_savgol(self, c, filter_width=5, polynomial_order=1):
        N = 10
        c = np.array(c)
        y = c[:, 1]
        x = c[:, 0]
        x2 = savgol_filter(x, filter_width, polynomial_order)
        y2 = savgol_filter(y, filter_width, polynomial_order)
        c = np.transpose([x2,y2])
        return c    
    # @iso_contours: input iso contours of a pocket
    # return a spiral contour
    def build_spiral_for_pocket(self, iso_contours):
        ## divide contours into two groups(by odd/even)
        if (len(iso_contours) == 1):
            return iso_contours[0]        
        in_contour_groups = []
        out_contour_groups = []
        for idx in range(len(iso_contours)):
            if (idx % 2 == 0):
                in_contour_groups.append(iso_contours[idx])
            else:
                out_contour_groups.append(iso_contours[idx])
    
    
        cc_in = self.contour2spiral(in_contour_groups, 0, self.offset )
        output_index = self.find_nearest_point_idx(in_contour_groups[0][0], out_contour_groups[0]) 
    
        cc_out = self.contour2spiral(out_contour_groups, output_index, self.offset )
    
        ## connect two spiral
        fspiral = self.connect_spiral(cc_in, cc_out)
        ## set out point
        out_point_index = self.find_point_index_by_distance(0, in_contour_groups[0], self.offset)
        fspiral.append(in_contour_groups[0][out_point_index])   
        ## smooth withe filter size 3, order 1
        fspiral = self.smooth_curve_by_savgol(fspiral, 3, 1)    
        return fspiral    

############################################################################################################
#                         Test Functions                                                                   #   
############################################################################################################   
####################################
# draw poly line to image #
# point_list is n*2 np.ndarray #
####################################
def draw_line(point_lists, img, color, line_width=1, point_size=0):
    point_lists = point_lists.astype(int)
    pts = point_lists.reshape((-1,1,2))
    cv2.polylines(img, [pts], False, color, thickness=line_width, lineType=cv2.LINE_AA)
    #cv2.imshow("Art", img)
    if point_size != 0:
        for p in point_lists:
            cv2.circle(img, tuple(p), point_size, color)   
    return
def draw_text(text, bottom_left, img, fontColor = (255,0,0), fontScale = 0.5, lineType=1):
    font                   = cv2.FONT_HERSHEY_SIMPLEX
    fontSize               = [12,-12]
    offset = bottom_left - np.array(fontSize)*fontScale
    cv2.putText(img,text,
        tuple(offset.astype(int)) ,
        font,
        fontScale,
        fontColor,
        lineType)
    return


           
############################
# compute hausdorff distance
############################

def compute_hausdorff_distance(c1, c2):
    u = np.array(c1)
    v = np.array(c2)
    return scid.directed_hausdorff(u, v)[0]   

def test_tree_visit(filepath):     
    pe = pathEngine()   
    pe.generate_contours_from_img(filepath, True)
    pe.im = cv2.cvtColor(pe.im, cv2.COLOR_GRAY2BGR)
    contour_tree = pe.convert_hiearchy_to_PyPolyTree()
   
    def func(node):
        contour = node.Contour
        if len(contour) == 0:
            return       
        draw_line(np.vstack([contour, contour[0]]), pe.im, (0,255,0),2)       
        return
    pe.traversing_PyPolyTree(contour_tree, func)  
    cv2.imshow("Art", pe.im)
    cv2.waitKey(0)               
    return

def test_region_contour(filepath):
    pe = pathEngine()   
    pe.generate_contours_from_img(filepath, True)
    pe.im = cv2.cvtColor(pe.im, cv2.COLOR_GRAY2BGR)
    contour_tree = pe.convert_hiearchy_to_PyPolyTree() 
    group_contour = pe.get_contours_from_each_connected_region(contour_tree, '0')
   
    #######################################
    # Generate N color list
    #################################
    def generate_RGB_list(N):
        import colorsys
        HSV_tuples = [(x*1.0/N, 0.8, 0.9) for x in range(N)]
        RGB_tuples = map(lambda x: colorsys.hsv_to_rgb(*x), HSV_tuples)
        rgb_list = tuple(RGB_tuples)
        return np.array(rgb_list) * 255  
    colors = generate_RGB_list(len(group_contour.values()))
    idx = 0
    for cs in group_contour.values():
        for c in cs:
            draw_line(np.vstack([c, c[0]]), pe.im, colors[idx],2)
        idx += 1
    cv2.imshow("Art", pe.im)
    cv2.waitKey(0)         
'''
pe.fill_closed_region_with_iso_contours(boundary, offset) return a 2d array c[i][j]
'''
def test_fill_with_iso_contour(filepath, reverseImage = True):
    offset = -6
    line_width = 1#int(abs(offset)/2)
    pe = pathEngine()   
    pe.generate_contours_from_img(filepath, reverseImage)
    pe.im = cv2.cvtColor(pe.im, cv2.COLOR_GRAY2BGR)
    contour_tree = pe.convert_hiearchy_to_PyPolyTree() 
    group_contour = pe.get_contours_from_each_connected_region(contour_tree, '0')
         
    #draw boundaries
    #################################
    # Generate N color list
    #################################
    def generate_RGB_list(N):
        import colorsys
        HSV_tuples = [(x*1.0/N, 0.8, 0.9) for x in range(N)]
        RGB_tuples = map(lambda x: colorsys.hsv_to_rgb(*x), HSV_tuples)
        rgb_list = tuple(RGB_tuples)
        return np.array(rgb_list) * 255  
    N = 50
    colors = generate_RGB_list(N)
   
    for boundary in group_contour.values():
        iso_contours = pe.fill_closed_region_with_iso_contours(boundary, offset)
        idx = 0
        for cs in iso_contours:
            for c in cs:
                draw_line(np.vstack([c, c[0]]), pe.im, colors[idx],line_width)
            idx += 1
    gray = cv2.cvtColor(pe.im, cv2.COLOR_BGR2GRAY)
    ret, mask = cv2.threshold(gray, 0, 255,cv2.THRESH_BINARY_INV |cv2.THRESH_OTSU)
    cv2.imshow("mask", mask)
    cv2.imwrite("d:/tmp.png", pe.im)  
    cv2.imshow("Art", pe.im)
    cv2.waitKey(0)             


  
if __name__ == '__main__':   
    #test_tree_visit("E:/git/suCAM/python/images/slice-1.png")
    #test_region_contour("E:/git/suCAM/python/images/slice-1.png")
    test_fill_with_iso_contour("E:/git/suCAM/python/images/slice-1.png")
    #test_segment_contours_in_region("E:/git/mydoc/Code/Python/gen_path/data/sample.png")
    #test_segment_contours_in_region("E:/git/suCAM/python/images/slice-1.png")
    