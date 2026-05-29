public class Problem01_SortList {
    static class ListNode{int val;ListNode next;ListNode(int v){val=v;}}
    
    static ListNode sortList(ListNode head) {
        if(head==null||head.next==null)return head;
        ListNode mid=getMid(head);ListNode second=mid.next;mid.next=null;
        return merge(sortList(head),sortList(second));
    }
    
    static ListNode getMid(ListNode h){ListNode s=h,f=h.next;while(f!=null&&f.next!=null){s=s.next;f=f.next.next;}return s;}
    
    static ListNode merge(ListNode a,ListNode b){
        ListNode d=new ListNode(0),c=d;
        while(a!=null&&b!=null){if(a.val<=b.val){c.next=a;a=a.next;}else{c.next=b;b=b.next;}c=c.next;}
        c.next=a!=null?a:b;return d.next;
    }
    
    public static void main(String[] args) {
        ListNode h=new ListNode(4);h.next=new ListNode(2);h.next.next=new ListNode(1);h.next.next.next=new ListNode(3);
        ListNode r=sortList(h);while(r!=null){System.out.print(r.val+" ");r=r.next;}System.out.println();
    }
}
