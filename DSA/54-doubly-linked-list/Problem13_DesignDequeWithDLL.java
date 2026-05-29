public class Problem13_DesignDequeWithDLL {
    static class Node { int val; Node prev, next; Node(int v){val=v;} }
    Node head=new Node(0),tail=new Node(0); int size=0;
    Problem13_DesignDequeWithDLL(){head.next=tail;tail.prev=head;}
    
    void pushFront(int v){Node n=new Node(v);n.next=head.next;n.prev=head;head.next.prev=n;head.next=n;size++;}
    void pushBack(int v){Node n=new Node(v);n.prev=tail.prev;n.next=tail;tail.prev.next=n;tail.prev=n;size++;}
    int popFront(){if(size==0)return -1;Node n=head.next;head.next=n.next;n.next.prev=head;size--;return n.val;}
    int popBack(){if(size==0)return -1;Node n=tail.prev;tail.prev=n.prev;n.prev.next=tail;size--;return n.val;}
    int peekFront(){return size==0?-1:head.next.val;}
    int peekBack(){return size==0?-1:tail.prev.val;}
    
    public static void main(String[] args) {
        Problem13_DesignDequeWithDLL dq=new Problem13_DesignDequeWithDLL();
        dq.pushFront(1);dq.pushBack(2);dq.pushFront(3);
        System.out.println(dq.popFront()+" "+dq.popBack()+" "+dq.popFront()); // 3 2 1
    }
}
