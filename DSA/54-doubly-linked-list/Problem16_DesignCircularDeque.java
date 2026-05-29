public class Problem16_DesignCircularDeque {
    static class Node{int val;Node prev,next;Node(int v){val=v;}}
    Node head=new Node(0),tail=new Node(0); int size,cap;
    Problem16_DesignCircularDeque(int k){cap=k;head.next=tail;tail.prev=head;}
    boolean insertFront(int v){if(size==cap)return false;Node n=new Node(v);n.next=head.next;n.prev=head;head.next.prev=n;head.next=n;size++;return true;}
    boolean insertLast(int v){if(size==cap)return false;Node n=new Node(v);n.prev=tail.prev;n.next=tail;tail.prev.next=n;tail.prev=n;size++;return true;}
    boolean deleteFront(){if(size==0)return false;Node n=head.next;head.next=n.next;n.next.prev=head;size--;return true;}
    boolean deleteLast(){if(size==0)return false;Node n=tail.prev;tail.prev=n.prev;n.prev.next=tail;size--;return true;}
    int getFront(){return size==0?-1:head.next.val;}
    int getRear(){return size==0?-1:tail.prev.val;}
    boolean isEmpty(){return size==0;}
    boolean isFull(){return size==cap;}
    
    public static void main(String[] args) {
        Problem16_DesignCircularDeque dq=new Problem16_DesignCircularDeque(3);
        System.out.println(dq.insertLast(1));dq.insertLast(2);dq.insertFront(3);
        System.out.println(dq.insertFront(4)); // false
        System.out.println(dq.getRear()); // 2
    }
}
