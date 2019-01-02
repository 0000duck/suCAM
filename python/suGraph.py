import numpy as np
'''
'''
class suNode():
    def __init__(self):
        self.pre = []
        self.next = []
        self.pocket_id = -1      # for connection between pocket   
    def get_number_of_path(self):
        return len(self.pre) + len(self.next)
    
        
'''
suGraph can be initialized by a relationaship matrix.
It aslo provides functions for clasification and visualizing
example:
    g = suGraph()
    g.init_from_matrix(R)
    g.classify_nodes_by_type(matrix) #classi
    g.to_Mathematica()  # to export graphPlot data for Mathematica
'''
class suGraph():
    def __init__(self):
        self.matrix = np.array(0)
        self.nodes = []
        return
    def init_from_matrix(self, matrix):
        self.matrix = matrix        
        self.nodes.clear()
        for i in range(len(matrix)):
            node = suNode()
            ids = np.argwhere(matrix[i] == 1)           
            node.next += list(ids.reshape(len(ids)) )
            ids = np.argwhere(matrix.T[i] == 1)
            node.pre += list(ids.reshape(len(ids)) )
            self.nodes.append(node)                 
    # simplify graph with info of contour layer
    def simplify_with_layer_info(self, map_ij):
        for i in range(len(self.nodes) ):
            for pre in self.nodes[i].pre():
                pre_node = self.nodes[pre]
                #if(map_ij[pre][0] == map_ij[i][0]:
                   
                   
        return
    def clear(self):
        self.matrix = np.array(0)
        return
    # @root_nodes: index list of all root nodes
    # Note: this algorithm can search classes from any node
    def classify_nodes_by_type(self, matrix):
        self.init_from_matrix(matrix)
        regions = []   #contour id groups
        pocket = []
        nodes_to_search = [0]   # outter contour
        
        done_ids = []
        while(len(nodes_to_search) != 0):
            idx = nodes_to_search.pop()                       
            if(self.nodes[idx].get_number_of_path() > 2):    #type_II node
                if(len(pocket) != 0):  # add last
                    regions.append(pocket.copy())   
                pocket.clear()
                #add itself as a single class
                pocket.append(idx)
                regions.append(pocket.copy())   
                pocket.clear()                
            else:
                pocket.append(idx)
                
            done_ids.append(idx)    
           
            #find other edges
            new_path = self.nodes[idx].pre + self.nodes[idx].next
            new_path = [x for x in new_path if (not x in done_ids) ]    #avoid re-enter
            if(len(new_path) == 0 and len(pocket) != 0): # end of path
                regions.append(pocket.copy())   
                pocket.clear()
            nodes_to_search += new_path                 
            
            #specify pocket id to node            
            if(len(regions) != 0):
                if(len(pocket) == 0):
                    self.nodes[idx].pocket_id = len(regions) - 1    # no new pocket
                else:
                    self.nodes[idx].pocket_id = len(regions)        # there's a new pocket.
            else:
                self.nodes[idx].pocket_id = 0            
        return regions    
    
    def connect_node_by_spiral(self, sprials):
        edges = []
        #traverse from node[0]
        done_ids = []
        nodes_to_search = [0]   # outter contour        
        spiral_node = []
        for i in range(len(self.nodes)):
            node = self.nodes[i]
            if(node.get_number_of_path() > 2):
                #check next and pre
                pocket_id = node.pocket_id
                #done_ids.append(i)
                for pre in node.pre:
                    #done_ids.append([self.nodes[pre].pocket_id, pocket_id])
                    done_ids.append([pre, i])
                for next in node.next:
                    #done_ids.append([pocket_id, self.nodes[next].pocket_id])
                    done_ids.append([i, next])
        print(np.asarray(done_ids).reshape(len(done_ids),2) + [1,1])
        for n in done_ids:
            cn = [self.nodes[n[0]].pocket_id, self.nodes[n[1]].pocket_id]
            print(cn)
                
                
            
        return 
        
    # visualization functions
    def to_Mathematica(self, filepath):
        np.set_printoptions(threshold=np.inf)
        script = 'GraphPlot[DATA, VertexLabeling -> True, MultiedgeStyle -> True(*,  DirectedEdges -> True*)]'
       
        sData = str(self.matrix)
        sData = sData.replace('\n', '')
        sData = sData.replace('[', '{')
        sData = sData.replace(']', '}')
        sData = sData.replace(' ', ', ')
        if(len(filepath) == 0):
            print(script.replace('DATA', sData))
        else:
            file = open(filepath,'w')
            file.write(script.replace('DATA', sData))
            file.close()
        return
