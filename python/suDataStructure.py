from collections import deque
import sys
#################################
# hold three dqeue simutaneously
#################################
class RDqueue():
    """
    A deque to hold r(i,j)
    """
    def __init__(self, R):
        """
        init with all regions in slices
        Note: It 
        """
        self.d = deque()
        self.di = deque()
        self.dj = deque()
        for i in range(len(R)):
            for j in range(len(R[i])):
                self.d.append(R[i][j])
                self.di.append(i)
                self.dj.append(j)         
        return
    def __len__(self):
        return len(self.d)
    def get_end(self):
        if len(self.di) > 0:
            r = self.d[0]
            i = self.di[0]
            j = self.dj[0]
            return r, i, j
        return [], sys.maxsize, -1

    def remove_end(self):
        self.d.popleft()
        self.di.popleft()
        self.dj.popleft()
        return
    def pop_end(self):
        r, i, j = self.get_end()
        if j != -1:
            self.remove_end()
        return
    def get_item(self, i, j):
        """
        Return r
        If r(i,j) is not found, return []
        """
        for idx in range(len(self.di)):
            if (self.di[idx] == i) and (self.dj[idx] == j ):
                return self.d[idx]
        return []
    def get_items(self, i):
        """
        return all r(i,*), js
        if not found return an empty list
        """
        rs = []     
        js = []
        for idx in range(len(self.d)):
            if self.di[idx] == i:
                rs.append(self.d[idx])
                js.append(self.dj[idx])
        return rs, js

    def remove_item(self, i, j):
        for idx in range(len(self.di)):
            if (self.di[idx] == i) and (self.dj[idx] == j ):                
                del self.di[idx]
                del self.dj[idx]
                del self.d[idx]
                break
        return   

    def size(self):
        return len(self.d)