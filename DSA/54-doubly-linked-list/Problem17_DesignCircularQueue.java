public class Problem17_DesignCircularQueue {
    static class Node{int val;Node prev,next;Node(int v){val=v;}}
    Node head=new Node(0),tail=new Node(0);int size,cap;
    Problem17_DesignCircularQueue(int k){cap=k;head.next=tail;tail.prev=head;}
    boolean enQueue(int v){if(size==cap)return false;Node n=new Node(v);n.prev=tail.prev;n.next=tail;tail.prev.next=n;tail.prev=n;size++;return true;}
    boolean deQueue(){if(size==0)return false;Node n=head.next;head.next=n.next;n.next.prev=head;size--;return true;}
    int Front(){return size==0?-1:head.next.val;}
    int Rear(){return size==0?-1:tail.prev.val;}
    boolean isEmpty(){return size==0;}
    boolean isFull(){return size==cap;}
    
    public static void main(String[] args) {
        Problem17_DesignCircularQueue q=new Problem17_DesignCircularQueue(3);
        q.enQueue(1);q.enQueue(2);q.enQueue(3);
        System.out.println(q.enQueue(4)); // false
        System.out.println(q.Rear()); // 3
        q.deQueue(); System.out.println(q.Front()); // 2
    }
}
