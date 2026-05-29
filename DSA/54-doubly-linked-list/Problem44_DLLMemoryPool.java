import java.util.*;

public class Problem44_DLLMemoryPool {
    static class Node{int id;boolean inUse;Node prev,next;Node(int i){id=i;}}
    Node freeHead=new Node(-1),freeTail=new Node(-1);
    Node usedHead=new Node(-1),usedTail=new Node(-1);
    Node[] pool;
    
    Problem44_DLLMemoryPool(int size){
        freeHead.next=freeTail;freeTail.prev=freeHead;
        usedHead.next=usedTail;usedTail.prev=usedHead;
        pool=new Node[size];
        for(int i=0;i<size;i++){pool[i]=new Node(i);addToList(freeHead,pool[i]);}
    }
    
    int allocate(){
        if(freeHead.next==freeTail)return -1;
        Node n=freeHead.next;removeFromList(n);addToList(usedHead,n);n.inUse=true;return n.id;
    }
    void free(int id){Node n=pool[id];if(!n.inUse)return;removeFromList(n);addToList(freeHead,n);n.inUse=false;}
    
    void addToList(Node head,Node n){n.next=head.next;n.prev=head;head.next.prev=n;head.next=n;}
    void removeFromList(Node n){n.prev.next=n.next;n.next.prev=n.prev;}
    
    public static void main(String[] args) {
        Problem44_DLLMemoryPool mp=new Problem44_DLLMemoryPool(5);
        System.out.println("Alloc: "+mp.allocate()); // 4 (LIFO from free list)
        System.out.println("Alloc: "+mp.allocate()); // 3
        mp.free(4);
        System.out.println("Alloc: "+mp.allocate()); // 4
    }
}
