'''
This module provides functions about filling path generation 
# 1. extract contours tree from mask image [simulating a layer of slices in STL model].
# 2. for each seperated region, generate iso-contours.
# 3. connect iso-contour to fermal spirals.
example:
          pe = pathEngine()
          im, contours, areas, hiearchy, root_contour_idx = pe.generate_contours_from_img(filename, isRevertBlackWhite)   
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

class pathEngine:
    def __init__(self):
        self.offset = 0.4
        self.im = None
        self.contours = None
        self.areas = None
        self.hiearchy = None  
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

############################################################################################################
#                         Test Functions                                                                   #    
############################################################################################################    
####################################
# draw poly line to image # 
# point_list is n*2 np.ndarray #
####################################
def draw_line(point_lists, img, color, line_width=1):
    point_lists = point_lists.astype(int)
    pts = point_lists.reshape((-1,1,2))
    cv2.polylines(img, [pts], False, color, thickness=line_width, lineType=cv2.LINE_AA)
    #cv2.imshow("Art", img)
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
def test_fill_with_iso_contour(filepath):
    offset = -6
    line_width = 1#int(abs(offset)/2)
    pe = pathEngine()    
    pe.generate_contours_from_img(filepath, True)
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
    
    cv2.imwrite("d:/tmp.png", pe.im)   
    cv2.imshow("Art", pe.im)
    cv2.waitKey(0)              

'''
test hausdorff distanse in  construct graph on iso-contours
'''
def test_segment_contours_in_region(filepath):
    offset = -15
    line_width = 1 #int(abs(offset)/2)
    pe = pathEngine()    
    pe.generate_contours_from_img(filepath, True)
    pe.im = cv2.cvtColor(pe.im, cv2.COLOR_GRAY2BGR)
    contour_tree = pe.convert_hiearchy_to_PyPolyTree()  
    group_contour = pe.get_contours_from_each_connected_region(contour_tree, '0')
    
    #################################
    # Add a child node
    # I use node.IsHole to save name
    #################################    
    def add_node(parent, contour, name=''):
        n = pyclipper.PyPolyNode()
        n.Contour = contour
        n.Parent = parent   
        n.depth = parent.depth + 1
        n.IsHole = name
        parent.Childs.append(n)
        return n
    #################################
    # Generate N color list
    #################################
    def generate_RGB_list(N):
        import colorsys
        HSV_tuples = [(x*1.0/N, 0.8, 0.9) for x in range(N)]
        RGB_tuples = map(lambda x: colorsys.hsv_to_rgb(*x), HSV_tuples)
        rgb_list = tuple(RGB_tuples)
        return np.array(rgb_list) * 255  
    ##################################################################
    # Get global index for contour(i,j) from iso_contours
    # Thus we can generate a index matrix for graph visualization in 
    # Mathematica:
    #    GraphPlot[{{1, 1, 1, 0}, {1, 0, 0, 0}, {0, 1, 0, 0}, {1, 1, 0, 1}}, 
    #               SelfLoopStyle -> True, MultiedgeStyle -> True, 
    #               VertexLabeling -> True, DirectedEdges -> True]
    ##################################################################    
    def get_contour_id(i,j,iso_contours):
        id = 0  
        ii = 0
        jj = 0
        for cs in iso_contours:
            if ii == i: break
            for c in cs:
                id += 1
            ii += 1            
        id += j # indexed from 0
        return id  
    
    N = 50
    colors = generate_RGB_list(N)
    
    # offset
    dist_th = abs(offset) * 1.1
    
    ## Compute disance matrix for each two layer
    ## Build a init graph from boundaries
    root = []
    iB = 0
    for boundary in group_contour.values():
        msg = "Region {}: has {} boundry contours.".format(iB, len(boundary))
        print(msg)
        
        iso_contours = pe.fill_closed_region_with_iso_contours(boundary, offset)        
        
        # init contour graph for each region
        num_contours = 0
        for cs in iso_contours:
            for c in cs:
                num_contours += 1         
        # @R is the relationship matrix
        R = np.zeros((num_contours, num_contours))        
        
        # @input: iso_contours c_{i,j}
        i = 0
        for cs in iso_contours[:-1]:     # for each group contour[i], where i*offset reprents the distance from boundaries       
            j1 = 0            
            for c1 in cs:                
                c1_id = get_contour_id(i, j1, iso_contours)
                draw_line(np.vstack([c1,c1[0]]), pe.im, colors[i], 1)               
                j2 = 0
                for c2 in iso_contours[i+1]:
                    dist = np.min(scid.cdist(c1, c2, 'euclidean') )
                    if(dist < dist_th):
                        c2_id = get_contour_id(i+1, j2, iso_contours)
                        R[c1_id][c2_id] = 1
                    j2 += 1
                j1 += 1
            i += 1        
        print(R)            
        iB += 1
    #for r in root:
        #pe.traversing_PyPolyTree(r)
        #visualize_tree("", r)
    
       
    cv2.imshow("Art", pe.im)
    cv2.waitKey(0)     
    
data = ""

def visualize_tree(filepath, root): 
    global data
    script = 'GraphPlot[{DATA}, VertexLabeling -> True]'
    
    def func(node):
        global data
        for c in node.Childs: 
            if node.depth != 0:
                data = data + '"' + str(node.IsHole) +'"' +  '->' + '"' + str(c.IsHole) + '" ,'
        return
    pe = pathEngine()   
    pe.traversing_PyPolyTree(root, func)   
    data = data.rstrip(',')
    print(script.replace('DATA', data))
    
    return    
if __name__ == '__main__':    
    #test_tree_visit("E:/git/suCAM/python/images/slice-1.png")
    #test_region_contour("E:/git/suCAM/python/images/slice-1.png")
    #test_fill_with_iso_contour("E:/git/suCAM/python/images/slice-1.png")
    #test_segment_contours_in_region("E:/git/suCAM/python/images/slice-1.png")
    test_segment_contours_in_region("E:/git/suCAM/python/images/slice-1.png")