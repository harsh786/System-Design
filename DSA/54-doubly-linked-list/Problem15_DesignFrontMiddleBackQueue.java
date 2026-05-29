import java.util.*;

public class Problem15_DesignFrontMiddleBackQueue {
    static class Node{int val;Node prev,next;Node(int v){val=v;}}
    Node head=new Node(0),tail=new Node(0); int size=0;
    Problem15_DesignFrontMiddleBackQueue(){head.next=tail;tail.prev=head;}
    
    void pushFront(int v){addAfter(head,v);}
    void pushMiddle(int v){Node mid=getMiddleNode();addAfter(mid,v);}
    void pushBack(int v){addAfter(tail.prev,v);}
    int popFront(){if(size==0)return -1;return remove(head.next);}
    int popMiddle(){if(size==0)return -1;Node mid=head;for(int i=0;i<(size+1)/2;i++)mid=mid.next;return remove(mid);}
    int popBack(){if(size==0)return -1;return remove(tail.prev);}
    
    Node getMiddleNode(){Node n=head;for(int i=0;i<size/2;i++)n=n.next;return n;}
    void addAfter(Node n,int v){Node nd=new Node(v);nd.next=n.next;nd.prev=n;n.next.prev=nd;n.next=nd;size++;}
    int remove(Node n){n.prev.next=n.next;n.next.prev=n.prev;size--;return n.val;}
    
    public static void main(String[] args) {
        Problem15_DesignFrontMiddleBackQueue q=new Problem15_DesignFrontMiddleBackQueue();
        q.pushFront(1);q.pushBack(2);q.pushMiddle(3);q.pushMiddle(4);
        System.out.println(q.popFront()); // 1
        System.out.println(q.popMiddle()); // 4
        System.out.println(q.popBack()); // 2
    }
}
